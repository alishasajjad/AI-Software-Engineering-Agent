from fastapi import (
    FastAPI,
    Response,
)
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
)

from app.api.v1.router import api_router
from app.core.config import settings

FAVICON_SVG = """
<svg
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 64 64"
>
  <defs>
    <linearGradient
      id="bg"
      x1="8"
      y1="6"
      x2="58"
      y2="60"
      gradientUnits="userSpaceOnUse"
    >
      <stop stop-color="#5EEAD4"/>
      <stop offset="1" stop-color="#38BDF8"/>
    </linearGradient>
  </defs>

  <rect
    x="3"
    y="3"
    width="58"
    height="58"
    rx="17"
    fill="#07111F"
  />

  <rect
    x="4"
    y="4"
    width="56"
    height="56"
    rx="16"
    fill="url(#bg)"
    fill-opacity="0.14"
    stroke="url(#bg)"
    stroke-width="2"
  />

  <path
    d="M24 21L14 32L24 43"
    fill="none"
    stroke="#FFFFFF"
    stroke-width="5"
    stroke-linecap="round"
    stroke-linejoin="round"
  />

  <path
    d="M40 21L50 32L40 43"
    fill="none"
    stroke="#FFFFFF"
    stroke-width="5"
    stroke-linecap="round"
    stroke-linejoin="round"
  />

  <path
    d="M36 17L28 47"
    fill="none"
    stroke="#5EEAD4"
    stroke-width="5"
    stroke-linecap="round"
  />
</svg>
""".strip()


def create_application() -> FastAPI:
    application = FastAPI(
        title=(
            "AI Software Engineering Agent API"
        ),
        description=(
            "Backend API for repository inspection, "
            "controlled code editing, human approval, "
            "verification and bounded self-correction."
        ),
        version="0.1.0",
        debug=settings.debug,
        docs_url=None,
        redoc_url=None,
    )

    application.include_router(
        api_router,
        prefix=settings.api_v1_prefix,
    )

    return application


app = create_application()


@app.get(
    "/favicon.svg",
    include_in_schema=False,
)
async def favicon_svg() -> Response:
    return Response(
        content=FAVICON_SVG,
        media_type="image/svg+xml",
    )


@app.get(
    "/favicon.ico",
    include_in_schema=False,
)
async def favicon_ico() -> Response:
    return Response(
        content=FAVICON_SVG,
        media_type="image/svg+xml",
    )


@app.get(
    "/docs",
    include_in_schema=False,
)
async def custom_swagger_docs():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=(
            "AI Software Engineering "
            "Agent API | Docs"
        ),
        swagger_favicon_url=(
            "/favicon.svg"
        ),
        swagger_ui_parameters={
            "displayRequestDuration": True,
            "filter": True,
            "persistAuthorization": True,
            "docExpansion": "none",
        },
    )


@app.get(
    "/redoc",
    include_in_schema=False,
)
async def custom_redoc():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=(
            "AI Software Engineering "
            "Agent API | ReDoc"
        ),
        redoc_favicon_url=(
            "/favicon.svg"
        ),
    )


@app.get(
    "/",
    tags=["Root"],
)
async def root() -> dict[str, str]:
    return {
        "message": (
            "AI Software Engineering Agent API"
        ),
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
    }