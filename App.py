from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import pandas as pd
import numpy as np
from PIL import Image
import io
import base64

app = FastAPI()

# This serves your web page when someone visits the main URL
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Fabric CAD Converter</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f7f6; padding: 15px; margin: 0; }
            .container { max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; font-size: 22px; }
            .upload-box { border: 2px dashed #ccc; padding: 20px; text-align: center; border-radius: 5px; margin-bottom: 20px; }
            button { background-color: #007bff; color: white; padding: 15px; border: none; border-radius: 5px; cursor: pointer; width: 100%; font-size: 18px; margin-top: 10px;}
            button:disabled { background-color: #aaa; }
            .download-btn { background-color: #28a745; margin-top: 15px; text-decoration: none; display: block; text-align: center; color: white; padding: 15px; border-radius: 5px; }
            #result { text-align: center; margin-top: 20px; }
            canvas { max-width: 100%; border: 1px solid #ddd; border-radius: 5px; display: none; margin-top: 15px; }
            .specs { font-weight: bold; color: #333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Greige Fabric Converter</h1>
            <p>Upload your Excel technical sheet to generate a fabric picture.</p>
            <div class="upload-box">
                <p><strong>Tap to select Excel file</strong></p>
                <input type="file" id="fileInput" accept=".xlsx, .xls" style="margin-top: 10px;">
            </div>
            <button id="processBtn" disabled>Process Technical Sheet</button>
            <div id="result"></div>
            <canvas id="fabricCanvas"></canvas>
            <a id="downloadLink" class="download-btn" style="display:none;">Download Image</a>
        </div>
        <script>
            const fileInput = document.getElementById('fileInput');
            const processBtn = document.getElementById('processBtn');
            const resultDiv = document.getElementById('result');
            const canvas = document.getElementById('fabricCanvas');
            const ctx = canvas.getContext('2d');
            const downloadLink = document.getElementById('downloadLink');
            let selectedFile = null;

            fileInput.addEventListener('change', (event) => {
                selectedFile = event.target.files[0];
                if (selectedFile) { processBtn.disabled = false; resultDiv.innerHTML = "<p>File ready. Tap Process.</p>"; }
            });

            processBtn.addEventListener('click', async () => {
                if (!selectedFile) return;
                resultDiv.innerHTML = "<p>Uploading to Cloud & Processing...</p>";
                const formData = new FormData();
                formData.append("file", selectedFile);

                try {
                    const response = await fetch('/upload/', { method: 'POST', body: formData });
                    const data = await response.json();
                    if (response.ok) {
                        resultDiv.innerHTML = `<h3>Generated Fabric</h3><p class="specs">Weave: ${data.weave}</p><p class="specs">EPI: ${data.epi} | PPI: ${data.ppi}</p>`;
                        const img = new Image();
                        img.onload = () => { ctx.drawImage(img, 0, 0, canvas.width, canvas.height); };
                        img.src = data.image;
                        canvas.style.display = "block";
                        downloadLink.href = data.image;
                        downloadLink.download = "generated_fabric.png";
                        downloadLink.style.display = "block";
                    } else {
                        resultDiv.innerHTML = `<p style="color:red;">Error: ${data.detail}</p>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<p style="color:red;">Connection failed.</p>`;
                }
            });
        </script>
    </body>
    </html>
    """

# This is the cloud backend engine that processes the file
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        data = df.iloc[0].to_dict()
        
        weave_type = str(data.get("Weave", "plain"))
        epi = int(data.get("EPI", 50))
        ppi = int(data.get("PPI", 50))
        
        # Generate Weave Matrix
        if "twill" in weave_type.lower() and "3/1" in weave_type:
            matrix = np.array([[1, 1, 1, 0], [0, 1, 1, 1], [1, 0, 1, 1], [1, 1, 0, 1]])
        else:
            matrix = np.array([[1, 0], [0, 1]])

        rows, cols = matrix.shape
        yarn_width_px = max(2, int(500 / epi)) 
        yarn_height_px = max(2, int(500 / ppi))
        
        img_width = cols * yarn_width_px * 5
        img_height = rows * yarn_height_px * 5
        
        img = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))
        pixels = img.load()
        warp_color = (50, 50, 50)
        weft_color = (200, 200, 200)

        for y in range(img_height):
            for x in range(img_width):
                matrix_col = (x // yarn_width_px) % cols
                matrix_row = (y // yarn_height_px) % rows
                pixels[x, y] = warp_color if matrix[matrix_row][matrix_col] == 1 else weft_color

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return JSONResponse(content={
            "message": "File processed successfully",
            "weave": weave_type,
            "epi": epi,
            "ppi": ppi,
            "image": f"data:image/png;base64,{img_str}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
