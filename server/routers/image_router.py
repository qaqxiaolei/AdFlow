from fastapi.responses import FileResponse, HTMLResponse, Response
from html import escape
from fastapi.concurrency import run_in_threadpool
from tools.utils.image_canvas_utils import generate_file_id
from services.config_service import FILES_DIR

from PIL import Image
from io import BytesIO
import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
import httpx
import aiofiles
from mimetypes import guess_type
from utils.http_client import HttpClient

router = APIRouter(prefix="/api")
os.makedirs(FILES_DIR, exist_ok=True)


def _video_watch_html(file_id: str) -> str:
    """免登录播放页：可播放；下载优先走分享；缓冲中不误报失败。"""
    safe = escape(file_id)
    stem = safe.rsplit(".", 1)[0]
    poster = f"/api/file/{stem}.jpg"
    src = f"/api/file/{safe}"
    download = f"/api/file/{safe}?download=1"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>视频播放</title>
<style>
  html,body{{margin:0;min-height:100%;background:#111;color:#fff;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
  .wrap{{min-height:100vh;display:flex;flex-direction:column;box-sizing:border-box;
    padding:12px 12px calc(16px + env(safe-area-inset-bottom))}}
  .stage{{position:relative;flex:1;min-height:52vh;background:#000;border-radius:12px;
    overflow:hidden;display:flex;align-items:center;justify-content:center}}
  video{{width:100%;height:100%;max-height:72vh;object-fit:contain;background:#000}}
  .loading{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:10px;background:rgba(0,0,0,.5);font-size:14px;color:#ddd;
    pointer-events:none;padding:16px;text-align:center}}
  .loading.hidden{{display:none}}
  .bar{{margin-top:14px;display:flex;flex-direction:column;gap:10px}}
  button.btn,a.btn{{display:block;width:100%;box-sizing:border-box;border:0;cursor:pointer;
    text-align:center;text-decoration:none;color:#111;background:#fff;border-radius:10px;
    padding:12px 16px;font-size:15px;font-weight:600;font-family:inherit}}
  button.btn:disabled{{opacity:.6}}
  .hint{{font-size:12px;line-height:1.55;color:#aaa;text-align:center;margin:0}}
</style>
</head>
<body>
<div class="wrap">
  <div class="stage">
    <video
      id="v"
      controls
      playsinline
      webkit-playsinline
      x5-playsinline
      x5-video-player-type="h5"
      x5-video-player-fullscreen="true"
      preload="auto"
      poster="{poster}"
      src="{src}"
    ></video>
    <div id="loading" class="loading">视频较大，正在缓冲，请稍候…</div>
  </div>
  <div class="bar">
    <button type="button" class="btn" id="dl">保存到手机</button>
    <p class="hint">手机网络较慢时可能要等一会儿才出画面，请先等待缓冲。<br/>保存时请选「存储到文件 / 存储视频」。若弹出「显示 / 下载」，请点「下载」。</p>
  </div>
</div>
<script>
(function(){{
  var v=document.getElementById('v');
  var loading=document.getElementById('loading');
  var dl=document.getElementById('dl');
  var src="{src}";
  var downloadUrl="{download}";
  var filename="{safe}";
  var isIOS=/iPhone|iPad|iPod/i.test(navigator.userAgent);
  var failTimer=null;
  var retries=0;

  function hideLoading(){{
    if(failTimer){{ clearTimeout(failTimer); failTimer=null; }}
    if(loading) loading.classList.add('hidden');
  }}
  function showLoading(msg){{
    if(!loading) return;
    loading.classList.remove('hidden');
    loading.textContent=msg||'视频较大，正在缓冲，请稍候…';
  }}
  function scheduleFailCheck(){{
    if(failTimer) clearTimeout(failTimer);
    // 手机缓冲很慢，不要过早判失败；等 90 秒仍无画面再提示保存
    failTimer=setTimeout(function(){{
      if(!v || v.readyState>=2 || v.currentTime>0) return;
      showLoading('缓冲较慢，可继续等待，或点下方保存到手机');
    }}, 90000);
  }}

  function tryPlay(){{
    if(!v) return;
    v.muted=true;
    var p=v.play();
    if(p&&p.then){{
      p.then(function(){{ try{{ v.muted=false; }}catch(e){{}} }})
       .catch(function(){{ /* 自动播放被拦：用户点控件即可 */ }});
    }}
  }}

  if(v){{
    v.addEventListener('loadstart', function(){{
      showLoading('视频较大，正在缓冲，请稍候…');
      scheduleFailCheck();
    }});
    v.addEventListener('waiting', function(){{
      showLoading('正在缓冲，请稍候…');
    }});
    v.addEventListener('playing', hideLoading);
    v.addEventListener('canplay', hideLoading);
    v.addEventListener('loadeddata', hideLoading);
    v.addEventListener('error', function(){{
      // 手机端常误报 error，先自动重试，不要立刻写「加载失败」
      var code=v.error && v.error.code;
      if(retries<2){{
        retries+=1;
        showLoading('网络波动，正在重试（'+retries+'/2）…');
        setTimeout(function(){{
          try{{ v.load(); tryPlay(); }}catch(e){{}}
          scheduleFailCheck();
        }}, 800);
        return;
      }}
      if(code===3 || code===4){{
        showLoading('当前环境无法直接播放，请点下方保存到手机');
      }} else {{
        showLoading('仍在加载，请稍候或点下方保存到手机');
        scheduleFailCheck();
      }}
    }});
    tryPlay();
    scheduleFailCheck();
  }}

  async function shareBlob(blob){{
    if(!navigator.share) return false;
    var file=new File([blob], filename, {{type: blob.type||'video/mp4'}});
    if(navigator.canShare && !navigator.canShare({{files:[file]}})) return false;
    await navigator.share({{files:[file], title: filename}});
    return true;
  }}

  function fallbackAnchorDownload(){{
    var a=document.createElement('a');
    a.href=downloadUrl;
    a.download=filename;
    a.rel='noopener';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }}

  if(dl){{
    dl.addEventListener('click', async function(){{
      dl.disabled=true;
      var old=dl.textContent;
      dl.textContent='准备中…';
      try{{
        var res=await fetch(src, {{credentials:'same-origin'}});
        if(!res.ok) throw new Error('HTTP '+res.status);
        var blob=await res.blob();
        if(isIOS){{
          var shared=await shareBlob(blob);
          if(shared) return;
        }}
        var objUrl=URL.createObjectURL(blob);
        var a=document.createElement('a');
        a.href=objUrl;
        a.download=filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function(){{ URL.revokeObjectURL(objUrl); }}, 2000);
      }} catch(e){{
        fallbackAnchorDownload();
      }} finally {{
        dl.disabled=false;
        dl.textContent=old;
      }}
    }});
  }}
}})();
</script>
</body>
</html>"""


async def ensure_video_poster(file_id: str) -> str | None:
    """vi_xxx.jpg 不存在时，从同名 mp4 抽一帧封面。"""
    lower = file_id.lower()
    if not lower.startswith('vi_') or not lower.endswith(('.jpg', '.jpeg')):
        return None
    poster_path = os.path.join(FILES_DIR, file_id)
    if os.path.exists(poster_path):
        return poster_path
    stem = file_id.rsplit('.', 1)[0]
    mp4_path = os.path.join(FILES_DIR, f'{stem}.mp4')
    if not os.path.exists(mp4_path):
        return None
    from tools.video_generation.mp4_faststart import extract_video_poster
    ok = await run_in_threadpool(extract_video_poster, mp4_path, poster_path)
    if ok and os.path.exists(poster_path):
        return poster_path
    return None

# 上传图片接口，支持表单提交
@router.post("/upload_image")
async def upload_image(file: UploadFile = File(...), max_size_mb: float = 3.0):
    print('🦄upload_image file', file.filename)
    # 生成文件 ID 和文件名
    file_id = generate_file_id()
    filename = file.filename or ''

    # Read the file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {e}")
    original_size_mb = len(content) / (1024 * 1024)  # Convert to MB

    # Open the image from bytes to get its dimensions
    with Image.open(BytesIO(content)) as img:
        width, height = img.size
        
        # Check if compression is needed
        if original_size_mb > max_size_mb:
            print(f'🦄 Image size ({original_size_mb:.2f}MB) exceeds limit ({max_size_mb}MB), compressing...')
            
            # Convert to RGB if necessary (for JPEG compression)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create a white background for transparent images
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Compress the image
            compressed_content = compress_image(img, max_size_mb)
            
            # Save compressed image using Image.save
            extension = 'jpg'  # Force JPEG for compressed images
            file_path = os.path.join(FILES_DIR, f'{file_id}.{extension}')
            
            # Create new image from compressed content and save
            with Image.open(BytesIO(compressed_content)) as compressed_img:
                width, height = compressed_img.size
                await run_in_threadpool(compressed_img.save, file_path, format='JPEG', quality=95, optimize=True)
                # compressed_img.save(file_path, format='JPEG', quality=95, optimize=True)
            
            final_size_mb = len(compressed_content) / (1024 * 1024)
            print(f'🦄 Compressed from {original_size_mb:.2f}MB to {final_size_mb:.2f}MB')
        else:
            # Determine the file extension from original file
            mime_type, _ = guess_type(filename)
            if mime_type and mime_type.startswith('image/'):
                extension = mime_type.split('/')[-1]
                # Handle common image format mappings
                if extension == 'jpeg':
                    extension = 'jpg'
            else:
                extension = 'jpg'  # Default to jpg for unknown types
            
            # Save original image using Image.save
            file_path = os.path.join(FILES_DIR, f'{file_id}.{extension}')
            
            # Determine save format based on extension
            save_format = 'JPEG' if extension.lower() in ['jpg', 'jpeg'] else extension.upper()
            if save_format == 'JPEG':
                img = img.convert('RGB')
            
            # img.save(file_path, format=save_format)
            await run_in_threadpool(img.save, file_path, format=save_format)

    # 返回文件信息
    print('🦄upload_image file_path', file_path)
    return {
        'file_id': f'{file_id}.{extension}',
        'url': f'/api/file/{file_id}.{extension}',
        'width': width,
        'height': height,
    }


def compress_image(img: Image.Image, max_size_mb: float) -> bytes:
    """
    Compress an image to be under the specified size limit.
    """
    # Start with high quality
    quality = 95
    
    while quality > 10:
        # Save to bytes buffer
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        
        # Check size
        size_mb = len(buffer.getvalue()) / (1024 * 1024)
        
        if size_mb <= max_size_mb:
            return buffer.getvalue()
        
        # Reduce quality for next iteration
        quality -= 10
    
    # If still too large, try reducing dimensions
    original_width, original_height = img.size
    scale_factor = 0.8
    
    while scale_factor > 0.3:
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Try with moderate quality
        buffer = BytesIO()
        resized_img.save(buffer, format='JPEG', quality=70, optimize=True)
        
        size_mb = len(buffer.getvalue()) / (1024 * 1024)
        
        if size_mb <= max_size_mb:
            return buffer.getvalue()
        
        scale_factor -= 0.1
    
    # Last resort: very low quality
    buffer = BytesIO()
    resized_img.save(buffer, format='JPEG', quality=30, optimize=True)
    return buffer.getvalue()


# 文件下载接口（显式支持 HEAD，供 CDN/播放器探测）
@router.head("/file/{file_id}")
async def head_file(file_id: str):
    file_path = os.path.join(FILES_DIR, f'{file_id}')
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    media_type, _ = guess_type(file_path)
    lower_name = file_id.lower()
    if lower_name.endswith('.mp4'):
        media_type = 'video/mp4'
    headers: dict[str, str] = {
        "Content-Length": str(os.path.getsize(file_path)),
    }
    if media_type and media_type.startswith('video/'):
        headers['Accept-Ranges'] = 'bytes'
    return Response(status_code=200, media_type=media_type, headers=headers)


@router.get("/file/{file_id}")
async def get_file(
    file_id: str,
    download: bool = Query(False),
    player: bool = Query(False),
):
    file_path = os.path.join(FILES_DIR, f'{file_id}')
    print('🦄get_file file_path', file_path)
    if not os.path.exists(file_path):
        poster_path = await ensure_video_poster(file_id)
        if poster_path:
            file_path = poster_path
        else:
            raise HTTPException(status_code=404, detail="File not found")

    media_type, _ = guess_type(file_path)
    lower_name = file_id.lower()
    if lower_name.endswith('.mp4'):
        media_type = 'video/mp4'
    elif lower_name.endswith('.webm'):
        media_type = 'video/webm'
    elif lower_name.endswith(('.jpg', '.jpeg')):
        media_type = 'image/jpeg'

    # 打开播放页时补做 faststart，让手机能边下边播（已处理过的文件会很快跳过）
    if player and lower_name.endswith('.mp4') and os.path.isfile(file_path):
        try:
            from tools.video_generation.mp4_faststart import apply_mp4_faststart
            await run_in_threadpool(apply_mp4_faststart, file_path)
        except Exception as exc:
            print(f"[faststart] lazy apply skipped: {exc}")

    if player and media_type and media_type.startswith('video/'):
        return HTMLResponse(_video_watch_html(file_id))

    headers: dict[str, str] = {}
    if media_type and media_type.startswith('video/'):
        headers['Accept-Ranges'] = 'bytes'
        headers['Cache-Control'] = 'public, max-age=3600'

    if download:
        return FileResponse(
            file_path,
            media_type=media_type or 'application/octet-stream',
            filename=file_id,
            headers=headers,
        )

    if media_type and media_type.startswith('video/'):
        headers['Content-Disposition'] = 'inline'
    return FileResponse(file_path, media_type=media_type, headers=headers)


@router.post("/comfyui/object_info")
async def get_object_info(data: dict):
    url = data.get('url', '')
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        timeout = httpx.Timeout(10.0)
        async with HttpClient.create(timeout=timeout) as client:
            response = await client.get(f"{url}/api/object_info")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code, detail=f"ComfyUI server returned status {response.status_code}")
    except Exception as e:
        if "ConnectError" in str(type(e)) or "timeout" in str(e).lower():
            print(f"ComfyUI connection error: {str(e)}")
            raise HTTPException(
                status_code=503, detail="ComfyUI server is not available. Please make sure ComfyUI is running.")
        print(f"Unexpected error connecting to ComfyUI: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to ComfyUI: {str(e)}")
