"""Context-aware visual selection.

Priority: (1) relevant figure from the learner's own PDF, (2) other indexed project visual,
(3) deterministic AI-specified educational SVG, (4) none. Generated visuals are always labeled.
"""
from __future__ import annotations
import html
from app.schemas import AIVisualSpec
from app.services import embeddings, vectorstore


async def pick_visual(db, *, user_id: str, project_id: str, question: str, cited: list[dict], spec: AIVisualSpec | None) -> tuple[dict | None, int]:
    """Returns (visual, visual_retrieval_count)."""
    cited_pages = {(c["material_id"], c["page"]) for c in cited}
    retrieved = 0
    # 1) figure on a cited page
    if cited_pages:
        q = {"project_id": project_id, "user_id": user_id, "$or": [{"material_id": m, "page": {"$gte": p - 1, "$lte": p + 1}} for m, p in cited_pages]}
        asset = await db.visual_assets.find_one(q)
        if asset:
            return _asset_visual(asset, "From your material (cited page)"), 1
    # 2) semantically similar figure anywhere in the project
    try:
        [vec] = await embeddings.embed([question])
        hits = vectorstore.search(vec, user_id=user_id, project_id=project_id, limit=3, extra={"type": "visual"})
        retrieved = len(hits)
        if hits and hits[0].score >= 0.45:
            asset = await db.visual_assets.find_one({"_id": hits[0].payload["chunk_id"], "project_id": project_id})
            if asset:
                return _asset_visual(asset, "From your material"), retrieved
    except Exception:  # noqa: BLE001
        pass
    # 3) generated deterministic SVG
    if spec and spec.kind != "none":
        svg = render_svg(spec)
        if svg:
            return {"source": "generated", "label": "AI-generated educational visual", "title": spec.title or "", "svg": svg,
                    "kind": spec.kind}, retrieved
    return None, retrieved


def _asset_visual(asset: dict, label: str) -> dict:
    return {"source": "material", "label": label, "title": asset.get("caption", ""), "asset_id": asset["_id"],
            "url": f"/api/materials/{asset['material_id']}/visuals/{asset['_id']}", "page": asset["page"], "material_id": asset["material_id"]}


# ---------------- deterministic SVG renderers ----------------
W = 640
FONT = "font-family='Inter, system-ui, sans-serif' font-size='13'"


def _e(s) -> str:
    return html.escape(str(s))


def render_svg(spec: AIVisualSpec) -> str | None:
    fn = {"sequence": _sequence, "layers": _layers, "steps": _steps, "array": _array, "network": _network,
          "curve": _curve, "table_relation": _table_relation, "tree": _tree}.get(spec.kind)
    if not fn:
        return None
    try:
        return fn(spec)
    except Exception:  # noqa: BLE001
        return None


def _wrap(body: str, h: int, title: str = "") -> str:
    t = f"<text x='16' y='24' font-weight='600' font-size='15' {FONT} fill='#1f2937'>{_e(title)}</text>" if title else ""
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {h}' width='100%' role='img' aria-label='{_e(title)}'>"
            f"<rect width='{W}' height='{h}' fill='#ffffff' rx='8'/>{t}{body}</svg>")


def _sequence(s: AIVisualSpec) -> str | None:
    actors = s.actors[:5] or ["A", "B"]
    msgs = s.messages[:8]
    if not msgs:
        return None
    top, gap = 60, 44
    h = top + 40 + gap * (len(msgs) + 1)
    xs = {a: 80 + i * ((W - 160) // max(1, len(actors) - 1)) if len(actors) > 1 else W // 2 for i, a in enumerate(actors)}
    body = ""
    for a, x in xs.items():
        body += f"<rect x='{x-55}' y='{top-24}' width='110' height='30' rx='6' fill='#e7efee' stroke='#2F5D62'/>"
        body += f"<text x='{x}' y='{top-4}' text-anchor='middle' {FONT} fill='#1f2937'>{_e(a)}</text>"
        body += f"<line x1='{x}' y1='{top+10}' x2='{x}' y2='{h-20}' stroke='#9ca3af' stroke-dasharray='4 4'/>"
    y = top + 40
    for m in msgs:
        fx, tx = xs.get(m.get("from"), xs[actors[0]]), xs.get(m.get("to"), xs[actors[-1]])
        d = 1 if tx >= fx else -1
        body += f"<line x1='{fx}' y1='{y}' x2='{tx - 8*d}' y2='{y}' stroke='#2F5D62' stroke-width='2' marker-end='url(#arr)'/>"
        body += f"<text x='{(fx+tx)//2}' y='{y-6}' text-anchor='middle' {FONT} fill='#374151'>{_e(m.get('label',''))}</text>"
        y += gap
    defs = "<defs><marker id='arr' markerWidth='8' markerHeight='8' refX='6' refY='4' orient='auto'><path d='M0,0 L8,4 L0,8 z' fill='#2F5D62'/></marker></defs>"
    return _wrap(defs + body, h, s.title)


def _layers(s: AIVisualSpec) -> str | None:
    items = s.items[:10]
    if not items:
        return None
    rh, top = 38, 44
    h = top + rh * len(items) + 20
    body = ""
    for i, it in enumerate(items):
        y = top + i * rh
        shade = 235 - i * 6
        body += f"<rect x='40' y='{y}' width='{W-80}' height='{rh-6}' rx='6' fill='rgb({shade},{shade+4},{shade+2})' stroke='#2F5D62'/>"
        body += f"<text x='{W//2}' y='{y+rh//2+2}' text-anchor='middle' {FONT} fill='#1f2937'>{_e(it)}</text>"
    return _wrap(body, h, s.title)


def _steps(s: AIVisualSpec) -> str | None:
    items = s.items[:8]
    if not items:
        return None
    bw, gap, top = 130, 24, 60
    per_row = 4
    rows = (len(items) + per_row - 1) // per_row
    h = top + rows * 110
    body = ""
    for i, it in enumerate(items):
        r, c = divmod(i, per_row)
        x, y = 30 + c * (bw + gap), top + r * 110
        body += f"<rect x='{x}' y='{y}' width='{bw}' height='64' rx='8' fill='#f3f7f6' stroke='#2F5D62'/>"
        body += f"<text x='{x+10}' y='{y+18}' {FONT} fill='#2F5D62' font-weight='600'>{i+1}</text>"
        for li, line in enumerate(_lines(it, 18)[:2]):
            body += f"<text x='{x+bw//2}' y='{y+38+li*16}' text-anchor='middle' {FONT} fill='#1f2937'>{_e(line)}</text>"
        if c < per_row - 1 and i < len(items) - 1:
            body += f"<text x='{x+bw+6}' y='{y+38}' font-size='18' fill='#6b7280'>→</text>"
    return _wrap(body, h, s.title)


def _array(s: AIVisualSpec) -> str | None:
    vals = s.values[:16]
    if not vals:
        return None
    cw = min(56, (W - 60) // len(vals))
    top, h = 60, 140
    body = ""
    for i, v in enumerate(vals):
        x = 30 + i * cw
        fill = "#2F5D62" if i in s.highlights else "#f3f7f6"
        col = "#ffffff" if i in s.highlights else "#1f2937"
        body += f"<rect x='{x}' y='{top}' width='{cw-4}' height='44' rx='4' fill='{fill}' stroke='#2F5D62'/>"
        body += f"<text x='{x+(cw-4)//2}' y='{top+27}' text-anchor='middle' {FONT} fill='{col}'>{_e(v)}</text>"
        body += f"<text x='{x+(cw-4)//2}' y='{top+62}' text-anchor='middle' font-size='11' {FONT} fill='#6b7280'>{i}</text>"
    return _wrap(body, h, s.title)


def _network(s: AIVisualSpec) -> str | None:
    sizes = [max(1, min(6, int(n))) for n in s.layer_sizes[:5]] or [3, 4, 2]
    h = 260
    xs = [80 + i * ((W - 160) // max(1, len(sizes) - 1)) for i in range(len(sizes))]
    pos = []
    for li, n in enumerate(sizes):
        ys = [50 + (j + 1) * (h - 60) // (n + 1) for j in range(n)]
        pos.append([(xs[li], y) for y in ys])
    body = ""
    for li in range(len(pos) - 1):
        for (x1, y1) in pos[li]:
            for (x2, y2) in pos[li + 1]:
                body += f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#cbd5d3' stroke-width='1'/>"
    labels = s.items[: len(sizes)] or ["Input", *["Hidden"] * (len(sizes) - 2), "Output"]
    for li, layer in enumerate(pos):
        for (x, y) in layer:
            body += f"<circle cx='{x}' cy='{y}' r='12' fill='#e7efee' stroke='#2F5D62' stroke-width='2'/>"
        body += f"<text x='{xs[li]}' y='{h-8}' text-anchor='middle' {FONT} fill='#374151'>{_e(labels[li] if li < len(labels) else '')}</text>"
    return _wrap(body, h, s.title)


def _curve(s: AIVisualSpec) -> str | None:
    h = 240
    pts = [(60 + i * 50, 50 + int(140 * (0.9 ** i) * (1 if i % 2 == 0 else 1.05))) for i in range(11)]
    path = "M" + " L".join(f"{x},{y}" for x, y in pts)
    body = (f"<line x1='50' y1='200' x2='{W-30}' y2='200' stroke='#9ca3af'/><line x1='50' y1='40' x2='50' y2='200' stroke='#9ca3af'/>"
            f"<path d='{path}' fill='none' stroke='#2F5D62' stroke-width='2.5'/>")
    xl = s.items[0] if s.items else "iterations"; yl = s.items[1] if len(s.items) > 1 else "loss"
    body += f"<text x='{W//2}' y='224' text-anchor='middle' {FONT} fill='#374151'>{_e(xl)}</text>"
    body += f"<text x='20' y='120' transform='rotate(-90 20 120)' text-anchor='middle' {FONT} fill='#374151'>{_e(yl)}</text>"
    return _wrap(body, h, s.title)


def _table_relation(s: AIVisualSpec) -> str | None:
    left, right = s.left[:6], s.right[:6]
    if not left or not right:
        return None
    rh, top = 26, 60
    h = top + rh * max(len(left), len(right)) + 30
    body = ""
    for i, v in enumerate(left):
        body += f"<rect x='40' y='{top+i*rh}' width='200' height='{rh-2}' fill='{'#e7efee' if i==0 else '#fff'}' stroke='#2F5D62'/><text x='50' y='{top+i*rh+17}' {FONT} fill='#1f2937'>{_e(v)}</text>"
    for i, v in enumerate(right):
        body += f"<rect x='400' y='{top+i*rh}' width='200' height='{rh-2}' fill='{'#e7efee' if i==0 else '#fff'}' stroke='#2F5D62'/><text x='410' y='{top+i*rh+17}' {FONT} fill='#1f2937'>{_e(v)}</text>"
    body += f"<line x1='240' y1='{top+rh//2}' x2='400' y2='{top+rh//2}' stroke='#2F5D62' stroke-width='2'/>"
    body += f"<text x='320' y='{top+rh//2-6}' text-anchor='middle' {FONT} fill='#374151'>{_e(s.items[0] if s.items else 'join key')}</text>"
    return _wrap(body, h, s.title)


def _tree(s: AIVisualSpec) -> str | None:
    root = s.root or (s.items[0] if s.items else "")
    if not root:
        return None
    levels = [[root]]
    seen = {root}
    for _ in range(3):
        nxt = [c for n in levels[-1] for c in s.children.get(n, [])[:4] if c not in seen]
        if not nxt:
            break
        seen.update(nxt); levels.append(nxt[:8])
    h = 60 + 80 * len(levels)
    pos = {}
    body = ""
    for li, lvl in enumerate(levels):
        for i, n in enumerate(lvl):
            x = (i + 1) * W // (len(lvl) + 1); y = 60 + li * 80
            pos[n] = (x, y)
    for parent, kids in s.children.items():
        if parent in pos:
            for k in kids:
                if k in pos:
                    body += f"<line x1='{pos[parent][0]}' y1='{pos[parent][1]+14}' x2='{pos[k][0]}' y2='{pos[k][1]-14}' stroke='#9ca3af'/>"
    for n, (x, y) in pos.items():
        body += f"<rect x='{x-50}' y='{y-14}' width='100' height='28' rx='14' fill='#e7efee' stroke='#2F5D62'/><text x='{x}' y='{y+5}' text-anchor='middle' {FONT} fill='#1f2937'>{_e(n[:16])}</text>"
    return _wrap(body, h, s.title)


def _lines(text: str, width: int) -> list[str]:
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out
