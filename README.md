# 🚀 Descargador de YouTube: Tu Solución Definitiva

¡Bienvenido a **Descargador de YouTube**, la aplicación web más intuitiva y poderosa para descargar contenido de YouTube! Con nuestra herramienta, podrás obtener tus videos y audios favoritos en cuestión de segundos, sin necesidad de conocimientos técnicos.

## 🎯 Objetivo del Proyecto

**Descargador de YouTube** es una aplicación web diseñada para permitirte descargar contenido de YouTube de manera sencilla y rápida. Podrás elegir entre:

- **Solo el audio** en formato MP3.
- **El video completo** en formato MP4.

## 🧩 Funcionamiento General

### Pantalla Principal (index.html)

- **Interfaz Limpia y Moderna**: Diseñada con Bootstrap para una experiencia de usuario fluida.
- **Campo para URL**: Simplemente pega la URL del video de YouTube que deseas descargar.
- **Información del Video**: Automáticamente se despliega la información del video, incluyendo título, canal, duración y miniatura.
- **Opciones de Descarga**: Elige entre descargar el audio en MP3 o el video completo en MP4 con un solo clic.

### Backend (app.py)

- **/**: Muestra la interfaz principal (index.html).
- **/get_video_info**: Recibe una URL por POST, analiza el video sin descargarlo y devuelve los metadatos como JSON (título, duración, miniatura, etc.).
- **/convert**: Recibe la URL y el formato (MP3/MP4), descarga el video usando `yt_dlp`, lo convierte si es necesario (usando FFmpeg) y devuelve el archivo listo para descargar.

### Componentes HTML

- **inputUrl.html**: Campo para pegar el enlace de YouTube.
- **instructions.html**: Instrucciones paso a paso para usar la aplicación.
- **Otros Componentes**: Muestran el video, botones de descarga, mensajes de estado, etc.

## 🛠️ Tecnologías Utilizadas

- **Flask**: Framework de Python para el backend.
- **yt_dlp**: Librería avanzada para manejar descargas de YouTube.
- **FFmpeg**: Herramienta para la conversión de formatos de audio y video.
- **Bootstrap**: Para una interfaz de usuario limpia y responsiva.

## 🧠 Conclusión

**Descargador de YouTube** es la herramienta perfecta para cualquier usuario que desee descargar contenido de YouTube sin complicaciones. Su estructura bien definida la hace ideal tanto para proyectos académicos como para futuras expansiones, como la integración con Telegram o la implementación de un historial de descargas.

## 🌐 Conéctate con Nosotros

¡Síguenos en nuestras redes sociales para estar al tanto de las últimas actualizaciones, novedades y consejos útiles!

- **[![Facebook](https://img.shields.io/badge/Facebook-1877F2?style=for-the-badge&logo=facebook&logoColor=white)](https://www.facebook.com/nico.sagastegui.7/)** ¡Únete a nuestra comunidad!
- **[![Twitter](https://img.shields.io/badge/Twitter-1DA1F2?style=for-the-badge&logo=twitter&logoColor=white)](https://x.com/i/flow/login?redirect_after_login=%2FNASCdev)** Síguenos para tweets exclusivos
- **[![Instagram](https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/nasc_dev/)** Descubre contenido visual inspirador
- **[![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/users/devnasc)** Únete a nuestro servidor y charla con la comunidad
- **[![TikTok](https://img.shields.io/badge/TikTok-000000?style=for-the-badge&logo=tiktok&logoColor=white)](https://www.tiktok.com/@nasc_dev)** Videos cortos y divertidos
- **[![Website](https://img.shields.io/badge/Website-4CAF50?style=for-the-badge&logo=google-chrome&logoColor=white)](https://mipropiapaginaweb.onrender.com/)** Explora más proyectos y recursos

---

¡Prueba **Descargador de YouTube** hoy mismo y descubre lo fácil que puede ser obtener tus videos y audios favoritos! 🎵🎬