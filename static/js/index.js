// #region Video information
async function getVideoInfo(url) {
    if (!url) return null;
    
    try {
        const response = await fetch("/get_video_info", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url })
        });
        
        if (!response.ok) throw new Error("Error fetching video info");
        
        return await response.json();
    } catch (err) {
        console.error("Error fetching video info:", err);
        return null;
    }
}
// #endregion

// #region Función convertir
async function convertir(formato) {
    const url = document.getElementById("url").value;
    const mensaje = document.getElementById("mensaje");
    const error = document.getElementById("error");
    const downloadButton = document.querySelector(formato === "mp3" ? 
        '.btn-danger' : '.btn-primary');
    const originalButtonText = downloadButton.innerHTML;

    error.textContent = "";
    mensaje.textContent = "";

    if (!url) {
        error.textContent = "Por favor, introduce un enlace de YouTube.";
        return;
    }

    // Disable button and show loading state
    downloadButton.disabled = true;
    downloadButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Descargando...`;
    mensaje.innerText = `Procesando ${formato.toUpperCase()}...`;

    try {
        const response = await fetch("/convert", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url, format: formato })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || "Error en la descarga");
        }

        const blob = await response.blob();
        const disposition = response.headers.get("Content-Disposition");
        let filename = formato === "mp3" ? "audio.mp3" : "video.mp4";

        if (disposition && disposition.includes("filename=")) {
            filename = disposition.split("filename=")[1].replaceAll('"', '');
        }

        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();

        mensaje.innerText = `¡${formato.toUpperCase()} descargado correctamente!`;
        launchConfetti();
    } catch (err) {
        console.error(err);
        error.textContent = `Error: ${err.message || "Ocurrió un error al convertir o descargar el video."}`;
    } finally {
        // Re-enable button and restore original text
        downloadButton.disabled = false;
        downloadButton.innerHTML = originalButtonText;
    }
}
// #endregion

// #region Miniatura dinámica
async function updateThumbnail() {
    const url = document.getElementById('url').value;
    const thumbnailContainer = document.getElementById('thumbnailContainer');
    const error = document.getElementById('error');
    const videoInfoContainer = document.getElementById('videoInfoContainer');
    
    error.textContent = "";
    thumbnailContainer.innerHTML = "";
    videoInfoContainer.innerHTML = "";
    
    if (!url) return;
    
    const videoId = getVideoId(url);
    
    if (!videoId) {
        error.textContent = "URL de YouTube inválida";
        return;
    }
    
    // Show loading indicator
    thumbnailContainer.innerHTML = '<div class="spinner-border text-light" role="status"><span class="visually-hidden">Cargando...</span></div>';
    
    // Try to get more detailed info from our API
    const videoInfo = await getVideoInfo(url);
    
    // Create thumbnail image
    thumbnailContainer.innerHTML = "";
    const img = document.createElement('img');
    
    if (videoInfo && videoInfo.thumbnail) {
        img.src = videoInfo.thumbnail;
    } else {
        img.src = `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`;
        img.onerror = function () {
            img.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
        };
    }
    
    img.alt = "Miniatura del video";
    img.className = "img-fluid rounded shadow-sm mb-3";
    thumbnailContainer.appendChild(img);
    
    // Display video info if available
    if (videoInfo) {
        videoInfoContainer.innerHTML = `
            <div class="card bg-dark text-white p-3 mb-3">
                <h5>${videoInfo.title || "Video de YouTube"}</h5>
                ${videoInfo.channel ? `<p class="mb-1"><small>Canal: ${videoInfo.channel}</small></p>` : ''}
                ${videoInfo.duration ? `<p class="mb-1"><small>Duración: ${formatDuration(videoInfo.duration)}</small></p>` : ''}
                ${videoInfo.views ? `<p class="mb-0"><small>Vistas: ${formatNumber(videoInfo.views)}</small></p>` : ''}
            </div>
        `;
    }
}

function getVideoId(url) {
    // This regex handles various YouTube URL formats
    const regexes = [
        /(?:youtube\.com\/(?:[^\/]+\/.*\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/,
        /^([^"&?\/\s]{11})$/ // Direct video ID
    ];
    
    for (const regex of regexes) {
        const match = url.match(regex);
        if (match) return match[1];
    }
    
    return null;
}

function formatDuration(seconds) {
    if (!seconds) return "Desconocida";
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hrs > 0) {
        return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}

function formatNumber(num) {
    return new Intl.NumberFormat().format(num);
}
// #endregion

// #region Confetti
function launchConfetti() {
    for (let i = 0; i < 100; i++) {
        createConfetti();
    }
}

function createConfetti() {
    const confetti = document.createElement("div");
    confetti.classList.add("confetti");
    confetti.style.left = Math.random() * 100 + "vw";
    confetti.style.animationDuration = Math.random() * 3 + 2 + "s";
    confetti.style.backgroundColor = getRandomColor();
    document.body.appendChild(confetti);
    setTimeout(() => confetti.remove(), 5000);
}

function getRandomColor() {
    const colors = ["#f94144", "#f3722c", "#f8961e", "#f9c74f", "#90be6d", "#43aa8b", "#577590"];
    return colors[Math.floor(Math.random() * colors.length)];
}
// #endregion

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    // Add input event listener for URL field
    const urlInput = document.getElementById('url');
    if (urlInput) {
        urlInput.addEventListener('input', function() {
            // Use debounce to avoid too many API calls while typing
            clearTimeout(urlInput.timer);
            urlInput.timer = setTimeout(updateThumbnail, 500);
        });
        
        // Handle paste event to immediately show thumbnail
        urlInput.addEventListener('paste', function() {
            setTimeout(updateThumbnail, 100);
        });
    }
});