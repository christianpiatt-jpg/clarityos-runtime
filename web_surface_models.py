# Auto-generated from web/src/contracts/webSurfaceV0_2.schema.json.
# DO NOT HAND-EDIT — run `bash scripts/gen_web_surface_models.sh` instead.
# The schema itself is generated from the canonical TypeScript contract
# at web/src/contracts/webSurfaceV0_2.ts; see docs/web_surface/v0.2.0-contract.md
# for the full bridge.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


class WebSurfaceV02(RootModel[Any]):
    root: Any = Field(..., title="WebSurfaceV0_2")


class RecordStringString(RootModel[dict[str, str]]):
    root: dict[str, str]


class RecordStringUnknown(RootModel[dict[str, Any]]):
    root: dict[str, Any]


class WebSurfaceV02ErrorEnvelope(BaseModel):
    """
    Stable error envelope. The `error` string is a machine-readable code (e.g. `"not_implemented"`, `"unauthorized"`); `detail` is an optional, opaque payload the caller may surface for diagnostics. Adding fields is allowed; removing or renaming `error` is a breaking change that requires a new contract version.
    """

    model_config = ConfigDict(
        extra="forbid",
    )
    detail: Any | None = None
    error: str


class WebSurfaceV02SurfaceAction1(BaseModel):
    """
    Discriminated union, keyed on `type`. Consumers exhaustively `switch` on `action.type` and TypeScript narrows the remaining fields. New action variants must be added before they are emitted; the absence of a default case in a switch is the compile-time guard that catches missed variants.

    Variants:   * `noop`      — explicit no-op; useful as a sentinel + as the                   first/safe entry in any reducer that needs a                   default case during migration.   * `render`    — render a named view, optionally with params.   * `navigate`  — change the current route path.
    """

    model_config = ConfigDict(
        extra="forbid",
    )
    type: Literal["noop"]


class WebSurfaceV02SurfaceAction3(BaseModel):
    """
    Discriminated union, keyed on `type`. Consumers exhaustively `switch` on `action.type` and TypeScript narrows the remaining fields. New action variants must be added before they are emitted; the absence of a default case in a switch is the compile-time guard that catches missed variants.

    Variants:   * `noop`      — explicit no-op; useful as a sentinel + as the                   first/safe entry in any reducer that needs a                   default case during migration.   * `render`    — render a named view, optionally with params.   * `navigate`  — change the current route path.
    """

    model_config = ConfigDict(
        extra="forbid",
    )
    path: str
    type: Literal["navigate"]


class Record3Cstring2Cstring3E(RootModel[dict[str, str]]):
    root: dict[str, str]


class Record3Cstring2Cunknown3E(RootModel[dict[str, Any]]):
    root: dict[str, Any]


class WebSurfaceV02Request(BaseModel):
    """
    Every Web Surface call carries this request shape.
    """

    model_config = ConfigDict(
        extra="forbid",
    )
    body: Any
    headers: Record3Cstring2Cstring3E
    method: str
    path: str


class WebSurfaceV02Response(BaseModel):
    """
    Every Web Surface call returns this response shape.
    """

    model_config = ConfigDict(
        extra="forbid",
    )
    body: Any
    headers: Record3Cstring2Cstring3E
    status: float


class WebSurfaceV02SurfaceAction2(BaseModel):
    """
    Discriminated union, keyed on `type`. Consumers exhaustively `switch` on `action.type` and TypeScript narrows the remaining fields. New action variants must be added before they are emitted; the absence of a default case in a switch is the compile-time guard that catches missed variants.

    Variants:   * `noop`      — explicit no-op; useful as a sentinel + as the                   first/safe entry in any reducer that needs a                   default case during migration.   * `render`    — render a named view, optionally with params.   * `navigate`  — change the current route path.
    """

    model_config = ConfigDict(
        extra="forbid",
    )
    params: Record3Cstring2Cunknown3E | None = None
    type: Literal["render"]
    view: str


class WebSurfaceV02SurfaceAction(
    RootModel[
        WebSurfaceV02SurfaceAction1
        | WebSurfaceV02SurfaceAction2
        | WebSurfaceV02SurfaceAction3
    ]
):
    root: WebSurfaceV02SurfaceAction1 | WebSurfaceV02SurfaceAction2 | WebSurfaceV02SurfaceAction3 = Field(
        ...,
        description="Discriminated union, keyed on `type`. Consumers exhaustively `switch` on `action.type` and TypeScript narrows the remaining fields. New action variants must be added before they are emitted; the absence of a default case in a switch is the compile-time guard that catches missed variants.\n\nVariants:   * `noop`      — explicit no-op; useful as a sentinel + as the                   first/safe entry in any reducer that needs a                   default case during migration.   * `render`    — render a named view, optionally with params.   * `navigate`  — change the current route path.",
    )
