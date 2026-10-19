import json
from html import escape

from fastapi import Request
from fastapi.responses import HTMLResponse


async def scalar_docs(request: Request) -> HTMLResponse:
    """Render the same reference from both the public API and legacy docs URLs."""
    root_path = request.scope.get("root_path", "").rstrip("/")
    schema_url = f"{root_path}/api/v1/api/docs/openapi"
    configuration = json.dumps(
        {
            "url": schema_url,
            "persistAuth": False,
            "telemetry": False,
            "withDefaultFonts": False,
        }
    ).replace("<", "\\u003c")
    title = escape(f"{request.app.title} · API 文档")
    return HTMLResponse(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>body {{ margin: 0; }} #status {{ padding: 24px; font-family: sans-serif; }}</style>
</head>
<body>
  <div id="status" role="status">正在加载 API 文档…</div>
  <div id="app"></div>
  <noscript>请启用 JavaScript 查看 API 文档。</noscript>
  <script type="module">
    const status = document.getElementById('status');
    try {{
      const {{ createApiReference }} = await import(
        'https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.69.2/esm.js'
      );
      const configuration = {configuration};
      const response = await fetch(configuration.url);
      if (!response.ok) throw new Error('OpenAPI 加载失败');
      const content = await response.json();
      if (!content.openapi || !content.paths) throw new Error('OpenAPI 格式无效');
      delete configuration.url;
      createApiReference('#app', {{ ...configuration, content }});
      status.remove();
    }} catch (error) {{
      status.textContent = 'API 文档加载失败，请检查网络连接后刷新页面。';
    }}
  </script>
</body>
</html>"""
    )
