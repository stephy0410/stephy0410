#!/usr/bin/env python3
"""Builds the burgundy SVG assets used by README.md.

Why generated instead of hand edited: every card shares one palette, one type
scale and one set of drawing helpers, so adding a project is a data change,
not a design job.

Setup (once):
    npm i @fontsource/instrument-serif @fontsource/instrument-sans @fontsource/ibm-plex-mono
    pip install fonttools brotli uharfbuzz

Run from the repo root:
    python3 tools/build_assets.py --fonts node_modules/@fontsource --out assets

Display type (names, titles) is converted to vector outlines so it renders the
same in every browser. Body text embeds a subset of the font covering all of
ASCII plus Spanish accents, so small text edits directly in the SVG are safe.
"""
import argparse
import base64
import io
import os
import random
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools import subset
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

# ---------------------------------------------------------------- content ---
CONTENT = {
    "name": "Stephanie Borrego",
    "tagline": [
        "Computer Systems Engineering student at ITESO.",
        "I build cloud systems and AI agents.",
    ],
    "terminal_title": "steph@guadalajara: ~",
    "terminal_cmd": "cat now.txt",
    "now": [
        ("shipped", "a multiagent support system on Bedrock AgentCore"),
        ("certified", "Future AWS Agent Engineer, Udacity"),
        ("learning", "distributed systems and system design"),
        ("open to", "new challenges and bigger problems"),
    ],
    "stack": [
        ("Code", ["Java", "Spring Boot", "Python", "JavaScript", "Node.js", "SQL"]),
        ("AWS", ["Lambda", "DynamoDB", "API Gateway", "ALB", "ElastiCache", "RDS",
                 "EventBridge", "SNS", "S3", "EC2", "ECR", "CloudWatch"]),
        ("Azure", ["AI Search", "Azure OpenAI", "Blob Storage", "Bicep",
                   "Power Automate"]),
        ("AI agents", ["Bedrock AgentCore", "Strands Agents", "RAG"]),
        ("Data", ["MySQL", "MongoDB", "Cassandra", "Neo4j", "Oracle Database",
                  "ChromaDB"]),
        ("Delivery", ["Terraform", "Docker", "GitHub Actions", "Cloudflare", "Git"]),
    ],
    "footer_title": "Let’s build something.",
    "footer_button": "Connect on LinkedIn",
}

# ---------------------------------------------------------------- palette ---
P = {
    "cellar": "#1C0610",     # deepest background
    "card": "#220713",       # card surface
    "edge": "#4E1124",       # outlines and separators
    "node": "#33101E",       # diagram node fill
    "node_stroke": "#7A2440",
    "burgundy": "#800020",   # primary: the part I built
    "garnet": "#A8324F",
    "rose": "#E8A0B4",       # accents, keys, arrows
    "blush": "#F6C9D5",
    "linen": "#F8EDEF",      # main text
}

FONT_FILES = {
    "serif": ("instrument-serif/files/instrument-serif-latin-400-normal.woff2", "SB Serif", 400),
    "serif_i": ("instrument-serif/files/instrument-serif-latin-400-italic.woff2", "SB Serif", 400),
    "sans": ("instrument-sans/files/instrument-sans-latin-400-normal.woff2", "SB Sans", 400),
    "sans_sb": ("instrument-sans/files/instrument-sans-latin-600-normal.woff2", "SB Sans", 600),
    "mono": ("ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2", "SB Mono", 400),
}
UNICODES = list(range(0x20, 0x7F)) + [ord(ch) for ch in "áéíóúñÁÉÍÓÚÑü¿¡‘’“”…"]

GITHUB_MARK = ("M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12")


# ------------------------------------------------------------------ fonts ---
class Font:
    def __init__(self, path, family, weight):
        self.data = open(path, "rb").read()
        self.family, self.weight = family, weight
        self.tt = TTFont(io.BytesIO(self.data))
        self.upm = self.tt["head"].unitsPerEm
        self.order = self.tt.getGlyphOrder()
        self.glyphs = self.tt.getGlyphSet()
        sfnt = TTFont(io.BytesIO(self.data))
        sfnt.flavor = None
        buf = io.BytesIO()
        sfnt.save(buf)
        self.hb = hb.Font(hb.Face(buf.getvalue()))
        self._face = None

    def _shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        return buf.glyph_infos, buf.glyph_positions

    def width(self, text, size):
        _, pos = self._shape(text)
        return sum(p.x_advance for p in pos) * size / self.upm

    def outline(self, text, x, y, size, anchor="start"):
        """Returns SVG path data for text, kerned by HarfBuzz."""
        infos, pos = self._shape(text)
        total = sum(p.x_advance for p in pos) * size / self.upm
        if anchor == "middle":
            x -= total / 2
        elif anchor == "end":
            x -= total
        s = size / self.upm
        pen_x, parts = 0, []
        for info, p in zip(infos, pos):
            pen = SVGPathPen(self.glyphs, ntos=lambda v: ("%.1f" % v).rstrip("0").rstrip("."))
            tx = x + (pen_x + p.x_offset) * s
            ty = y - p.y_offset * s
            self.glyphs[self.order[info.codepoint]].draw(TransformPen(pen, (s, 0, 0, -s, tx, ty)))
            parts.append(pen.getCommands())
            pen_x += p.x_advance
        return " ".join(part for part in parts if part)

    def face(self):
        """@font-face rule with a woff2 subset embedded as a data URI."""
        if self._face is None:
            t = TTFont(io.BytesIO(self.data))
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga", "calt"]
            sub = subset.Subsetter(opts)
            sub.populate(unicodes=UNICODES)
            sub.subset(t)
            t.flavor = "woff2"
            buf = io.BytesIO()
            t.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode()
            self._face = (f"@font-face{{font-family:'{self.family}';font-weight:{self.weight};"
                          f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
        return self._face


BASE_CSS = (
    ".sans{font-family:'SB Sans','Helvetica Neue',Helvetica,Arial,sans-serif}"
    ".mono{font-family:'SB Mono',Menlo,Consolas,monospace}"
)


def svg_doc(w, h, title, body, fonts=(), css=""):
    faces = "".join(f.face() for f in fonts)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
            f"<title>{escape(title)}</title><style>{faces}{BASE_CSS}{css}</style>{body}</svg>")


def text(x, y, s, size, fill, cls="sans", weight=400, anchor="start", opacity=1, extra=""):
    op = f' opacity="{opacity}"' if opacity != 1 else ""
    return (f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{op}{extra}>{escape(s)}</text>')


def stars(rnd, n, w, y0, y1):
    out = []
    for _ in range(n):
        out.append(f'<circle cx="{rnd.uniform(0, w):.1f}" cy="{rnd.uniform(y0, y1):.1f}" '
                   f'r="{rnd.uniform(.6, 1.5):.2f}" fill="{P["linen"]}" opacity="{rnd.uniform(.12, .5):.2f}"/>')
    return "".join(out)


def blur_filter(fid, std):
    return (f'<filter id="{fid}" x="-60%" y="-60%" width="220%" height="220%">'
            f'<feGaussianBlur stdDeviation="{std}"/></filter>')


# ----------------------------------------------------------------- header ---
def build_header(F):
    W, H, HZ, VX = 1200, 400, 268, 930
    rnd = random.Random(7)
    name = CONTENT["name"]
    size = min(100, 690 / F["serif"].width(name, 1))
    name_path = F["serif"].outline(name, 72, 152, size)

    vlines = "".join(f'<line x1="{VX}" y1="{HZ}" x2="{VX + k * 80}" y2="{H}"/>' for k in range(-28, 27))
    hlines = []
    for i in range(-9, 20):
        y = HZ + 2.6 * 1.42 ** i
        if y > H + 90:
            break
        hlines.append(f'<line x1="0" y1="{y:.2f}" x2="{W}" y2="{y:.2f}"/>')
    slits = "".join(f'<rect x="0" y="{y}" width="{W}" height="{h}" fill="#000"/>'
                    for y, h in [(HZ - 14, 9), (HZ - 34, 6.5), (HZ - 52, 4.5), (HZ - 68, 3), (HZ - 82, 1.8)])

    css = (".h{transform-box:view-box;transform-origin:0px %dpx;animation:drift 3.2s linear infinite}"
           "@keyframes drift{from{transform:scaleY(1)}to{transform:scaleY(1.42)}}"
           "@media (prefers-reduced-motion:reduce){.h{animation:none}}" % HZ)
    tag = "".join(text(74, 210 + 36 * i, line, 25, P["blush"], opacity=.92) for i, line in enumerate(CONTENT["tagline"]))

    body = f"""<defs>
<clipPath id="r"><rect width="{W}" height="{H}" rx="24"/></clipPath>
<clipPath id="above"><rect width="{W}" height="{HZ}"/></clipPath>
<clipPath id="floor"><rect y="{HZ}" width="{W}" height="{H - HZ}"/></clipPath>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="{HZ}" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="#12030A"/><stop offset=".5" stop-color="#2C0814"/>
<stop offset=".85" stop-color="#5A1027"/><stop offset="1" stop-color="#7C1A35"/></linearGradient>
<linearGradient id="sun" x1="0" y1="{HZ - 150}" x2="0" y2="{HZ}" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="#FCE6EC"/><stop offset=".5" stop-color="{P['rose']}"/><stop offset="1" stop-color="{P['garnet']}"/></linearGradient>
<linearGradient id="fade" x1="0" y1="{HZ}" x2="0" y2="{H}" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="#fff" stop-opacity=".04"/><stop offset=".45" stop-color="#fff" stop-opacity=".5"/>
<stop offset="1" stop-color="#fff" stop-opacity=".95"/></linearGradient>
<mask id="slits"><rect width="{W}" height="{H}" fill="#fff"/>{slits}</mask>
<mask id="floorfade"><rect y="{HZ}" width="{W}" height="{H - HZ}" fill="url(#fade)"/></mask>
{blur_filter('b40', 40)}{blur_filter('b18', 18)}{blur_filter('b5', 5)}
</defs>
<g clip-path="url(#r)">
<rect width="{W}" height="{HZ}" fill="url(#sky)"/>
{stars(rnd, 70, W, 14, HZ - 30)}
<circle cx="{VX}" cy="{HZ}" r="190" fill="{P['rose']}" opacity=".26" filter="url(#b40)"/>
<g clip-path="url(#above)"><circle cx="{VX}" cy="{HZ}" r="150" fill="url(#sun)" mask="url(#slits)"/></g>
<rect y="{HZ}" width="{W}" height="{H - HZ}" fill="#14030A"/>
<ellipse cx="{VX}" cy="{HZ + 20}" rx="280" ry="36" fill="{P['rose']}" opacity=".2" filter="url(#b18)"/>
<g clip-path="url(#floor)"><g mask="url(#floorfade)" stroke="{P['rose']}" stroke-width="1.1" fill="none">
<g>{vlines}</g><g class="h">{''.join(hlines)}</g></g></g>
<line x1="0" y1="{HZ}" x2="{W}" y2="{HZ}" stroke="{P['rose']}" stroke-width="6" opacity=".55" filter="url(#b5)"/>
<line x1="0" y1="{HZ}" x2="{W}" y2="{HZ}" stroke="#FBD9E2" stroke-width="1.6"/>
<path d="{name_path}" fill="{P['linen']}"/>
{tag}
</g>"""
    title = f"{name}. " + " ".join(CONTENT["tagline"])
    return svg_doc(W, H, title, body, fonts=[F["sans"]], css=css)


# --------------------------------------------------------------- terminal ---
def build_now(F):
    W, H = 1200, 372
    mono = F["mono"]
    fs = 21
    cw = mono.width("M", fs)
    x0, key_w = 48, cw * 11
    y_cmd, step = 108, 44
    parts, covers = [], []
    delay = 0.3

    def cover(y, x_end, dur, steps, start):
        w = x_end - x0 + 10
        covers.append(f'<rect class="cv" x="{x0 - 4}" y="{y - 26}" width="{w:.1f}" height="36" fill="{P["cellar"]}" '
                      f'style="animation:type {dur}s steps({steps}) {start:.2f}s both"/>')

    cmd = CONTENT["terminal_cmd"]
    parts.append(text(x0, y_cmd, "$", fs, P["rose"], cls="mono"))
    parts.append(text(x0 + 2 * cw, y_cmd, cmd, fs, P["linen"], cls="mono"))
    cover(y_cmd, x0 + (2 + len(cmd)) * cw, 0.7, len(cmd) + 2, delay)
    t = delay + 1.0
    y = y_cmd
    for key, val in CONTENT["now"]:
        y += step
        parts.append(text(x0, y, key, fs, P["rose"], cls="mono"))
        parts.append(text(x0 + key_w, y, val, fs, P["linen"], cls="mono", opacity=.95))
        end = x0 + key_w + mono.width(val, fs)
        cover(y, end, 0.55, 24, t)
        t += 0.7
    y += step + 4
    parts.append(text(x0, y, "$", fs, P["rose"], cls="mono"))
    parts.append(f'<rect class="cur" x="{x0 + 2 * cw:.1f}" y="{y - 18}" width="{cw * .9:.1f}" height="23" fill="{P["rose"]}" '
                 f'style="animation:blink 1.1s steps(1) {t + .1:.2f}s infinite"/>')
    cover(y, x0 + 3 * cw, 0.2, 2, t)

    css = (".cv{transform-box:fill-box;transform-origin:right center}"
           "@keyframes type{from{transform:scaleX(1)}to{transform:scaleX(0)}}"
           "@keyframes blink{0%{opacity:1}50%{opacity:0}}"
           "@media (prefers-reduced-motion:reduce){.cv{display:none}.cur{animation:none!important}}")
    dots = "".join(f'<circle cx="{30 + 24 * i}" cy="23" r="6.5" fill="{c}"/>'
                   for i, c in enumerate([P["burgundy"], P["garnet"], P["rose"]]))
    body = f"""<defs><clipPath id="r"><rect width="{W}" height="{H}" rx="18"/></clipPath></defs>
<g clip-path="url(#r)"><rect width="{W}" height="{H}" fill="{P['cellar']}"/>
<rect width="{W}" height="46" fill="#2A0A16"/>{dots}
{text(W / 2, 29, CONTENT['terminal_title'], 15, P['linen'], cls='mono', anchor='middle', opacity=.55)}
<line x1="0" y1="46" x2="{W}" y2="46" stroke="{P['edge']}"/>
{''.join(parts)}{''.join(covers)}</g>
<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="18" fill="none" stroke="{P['edge']}" stroke-width="1.5"/>"""
    title = "Terminal showing what Stephanie is doing now. " + ". ".join(f"{k}: {v}" for k, v in CONTENT["now"])
    return svg_doc(W, H, title, body, fonts=[mono], css=css)


# ------------------------------------------------------------------ cards ---
CW, CH = 600, 360
EDGE_CSS = (".e{fill:none;stroke:#D98AA2;stroke-width:1.6;opacity:.9}")


def node(x, y, w, h, label, sub=None, accent=False):
    fill, stroke = (P["burgundy"], P["rose"]) if accent else (P["node"], P["node_stroke"])
    cx, cy = x + w / 2, y + h / 2
    out = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>'
    if sub:
        out += text(cx, cy - 2, label, 15, P["linen"], weight=600, anchor="middle")
        out += text(cx, cy + 16, sub, 12.5, P["blush"] if accent else P["rose"], anchor="middle", opacity=.9)
    else:
        out += text(cx, cy + 5, label, 15, P["linen"], weight=600, anchor="middle")
    return out


def edge(d, both=False):
    start = ' marker-start="url(#ah)"' if both else ""
    return f'<path class="e" d="{d}" marker-end="url(#ah)"{start}/>'


def card(F, title, context, desc, diagram, alt):
    t_path = F["serif"].outline(title, 36, 72, 40)
    desc_svg = "".join(text(36, 140 + 26 * i, line, 18.5, P["linen"], opacity=.92) for i, line in enumerate(desc))
    body = f"""<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
<path d="M0 0L10 5L0 10z" fill="#D98AA2"/></marker></defs>
<rect x=".75" y=".75" width="{CW - 1.5}" height="{CH - 1.5}" rx="20" fill="{P['card']}" stroke="{P['edge']}" stroke-width="1.5"/>
<path d="{t_path}" fill="{P['linen']}"/>
<path transform="translate(540 47)" d="{GITHUB_MARK}" fill="{P['rose']}" opacity=".8"/>
{text(36, 102, context, 15.5, P['rose'])}
{desc_svg}
{diagram}"""
    return svg_doc(CW, CH, alt, body, fonts=[F["sans"], F["sans_sb"]], css=EDGE_CSS)


def card_phish_guard(F):
    d = node(36, 206, 124, 62, "Web page", "untrusted input")
    d += node(194, 198, 156, 78, "Phish Guard", "Strands agent scan", accent=True)
    d += node(400, 186, 164, 52, "Agent continues", "page is clean")
    d += node(400, 262, 164, 52, "Page blocked", "injection found")
    d += edge("M160 237H192")
    d += edge("M350 237C376 237 374 212 398 212")
    d += edge("M350 237C376 237 374 288 398 288")
    return card(F, "Agent Phish Guard", "AWS Builder Center hackathon, team lead",
                ["Scans web pages for hidden prompt injection", "before an AI agent reads and acts on them."], d,
                "Agent Phish Guard. Scans web pages for hidden prompt injection before an AI agent acts on them. "
                "Flow: web page, Phish Guard Strands agent scan, then the agent continues or the page is blocked.")


def card_pricewatch(F):
    xs = [36, 174, 312, 450]
    labels = [("EventBridge", "every 30 min"), ("Lambda", "Docker scraper"),
              ("DynamoDB", "price history"), ("SNS", "email alert")]
    d = "".join(node(x, 210, 114, 62, a, b, accent=(i == 1)) for i, (x, (a, b)) in enumerate(zip(xs, labels)))
    d += "".join(edge(f"M{x + 114} 241H{x + 136}") for x in xs[:-1])
    d += text(36, 318, "Plus a REST API on Lambda and a dashboard hosted on S3.", 14.5, P["linen"], opacity=.72)
    return card(F, "PriceWatch", "Team of three. I owned the backend, API and frontend",
                ["Watches prices in six Mexican online stores", "and emails you when one drops below your target."], d,
                "PriceWatch. Serverless price tracker on AWS. EventBridge every 30 minutes triggers a Lambda scraper "
                "in Docker, prices go to DynamoDB, and SNS sends an email alert.")


def card_cache_api(F):
    d = node(36, 206, 112, 62, "ALB", "load balancer")
    d += node(180, 198, 168, 78, "Lambda", "cache aside, key locks", accent=True)
    d += node(392, 186, 172, 52, "ElastiCache", "hot reads, TTL jitter")
    d += node(392, 262, 172, 52, "RDS PostgreSQL", "on a cache miss")
    d += edge("M148 237H178")
    d += edge("M348 237C372 237 368 212 390 212", both=True)
    d += edge("M348 237C372 237 368 288 390 288", both=True)
    return card(F, "Serverless Cache API", "Distributed systems course, built with Terraform",
                ["Read heavy catalog API with a cache in front of", "the database. Under load: 15x throughput, p99 132 ms."], d,
                "Serverless Cache API. Read heavy catalog API on AWS: ALB, Lambda with cache aside and per key locks, "
                "ElastiCache and RDS PostgreSQL, provisioned with Terraform. Under a 300 requests per second load test, "
                "successful throughput rose 15x and p99 latency fell from 20 seconds to 132 milliseconds.")


def card_social(F):
    d = node(36, 222, 150, 72, "Analytics API", "one entry point", accent=True)
    stores = [("MongoDB", "documents"), ("Cassandra", "time series logs"),
              ("Dgraph", "relationships"), ("ChromaDB + LLM", "semantic search")]
    for i, (a, b) in enumerate(stores):
        y = 186 + 40 * i
        d += f'<rect x="300" y="{y}" width="264" height="32" rx="8" fill="{P["node"]}" stroke="{P["node_stroke"]}" stroke-width="1.3"/>'
        d += text(314, y + 21, a, 14.5, P["linen"], weight=600)
        d += text(550, y + 21, b, 12.5, P["rose"], anchor="end", opacity=.9)
        d += edge(f"M186 258C244 258 240 {y + 16} 298 {y + 16}")
    return card(F, "Social Analytics Tool", "Final project, NoSQL databases course",
                ["One analytics API on top of four databases,", "each chosen for the query it answers best."], d,
                "Social Analytics Tool. One analytics API over MongoDB for documents, Cassandra for time series logs, "
                "Dgraph for relationships and ChromaDB with an LLM for semantic search.")


# ------------------------------------------------------------------ stack ---
def build_stack(F):
    W = 1200
    sans, sb = F["sans"], F["sans_sb"]
    x_chip0, x_max, chip_h, gap = 228, 1160, 38, 9
    y, parts = 34, []
    for r, (label, items) in enumerate(CONTENT["stack"]):
        if r:
            parts.append(f'<line x1="48" y1="{y - 12}" x2="{W - 48}" y2="{y - 12}" stroke="{P["edge"]}"/>')
        row_top = y
        x = x_chip0
        for item in items:
            cw = sans.width(item, 16.5) + 30
            if x + cw > x_max:
                x = x_chip0
                y += chip_h + 10
            parts.append(f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{chip_h}" rx="{chip_h / 2}" '
                         f'fill="{P["node"]}" stroke="{P["node_stroke"]}" stroke-width="1.2"/>')
            parts.append(text(x + cw / 2, y + 25, item, 16.5, P["linen"], anchor="middle"))
            x += cw + gap
        parts.append(f'<path d="{F["serif_i"].outline(label, 48, row_top + 28, 29)}" fill="{P["rose"]}"/>')
        y += chip_h + 24
    H = y + 10
    body = (f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="18" fill="{P["cellar"]}" '
            f'stroke="{P["edge"]}" stroke-width="1.5"/>' + "".join(parts))
    alt = "Tech stack. " + ". ".join(f"{label}: {', '.join(items)}" for label, items in CONTENT["stack"])
    return svg_doc(W, H, alt, body, fonts=[sans, sb])


# ----------------------------------------------------------------- footer ---
def build_footer(F):
    W, H = 1200, 280
    rnd = random.Random(11)
    sb = F["sans_sb"]
    head = F["serif"].outline(CONTENT["footer_title"], W / 2, 106, 62, anchor="middle")
    btn = CONTENT["footer_button"]
    bw = sb.width(btn, 19) + 60
    bx = (W - bw) / 2
    slits = "".join(f'<rect x="0" y="{y}" width="{W}" height="{h}" fill="#000"/>'
                    for y, h in [(H - 12, 8), (H - 30, 6), (H - 46, 4), (H - 60, 2.5)])
    body = f"""<defs>
<clipPath id="r"><rect width="{W}" height="{H}" rx="24"/></clipPath>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="{H}" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="#12030A"/><stop offset=".55" stop-color="#2C0814"/><stop offset="1" stop-color="#6A1530"/></linearGradient>
<linearGradient id="sun" x1="0" y1="{H - 90}" x2="0" y2="{H}" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="#FCE6EC"/><stop offset=".6" stop-color="{P['rose']}"/><stop offset="1" stop-color="{P['garnet']}"/></linearGradient>
<mask id="slits"><rect width="{W}" height="{H}" fill="#fff"/>{slits}</mask>
{blur_filter('b40', 40)}
</defs>
<g clip-path="url(#r)">
<rect width="{W}" height="{H}" fill="url(#sky)"/>
{stars(rnd, 50, W, 10, H - 40)}
<circle cx="{W / 2}" cy="{H + 40}" r="170" fill="{P['rose']}" opacity=".25" filter="url(#b40)"/>
<circle cx="{W / 2}" cy="{H + 40}" r="128" fill="url(#sun)" mask="url(#slits)"/>
<path d="{head}" fill="{P['linen']}"/>
<rect x="{bx:.1f}" y="134" width="{bw:.1f}" height="52" rx="26" fill="{P['burgundy']}" stroke="{P['rose']}" stroke-width="1.5"/>
{text(W / 2, 167, btn, 19, P['linen'], weight=600, anchor='middle')}
</g>"""
    return svg_doc(W, H, f"{CONTENT['footer_title']} {btn}.", body, fonts=[sb])


# ------------------------------------------------------------------- main ---
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default="node_modules/@fontsource")
    ap.add_argument("--out", default="assets")
    args = ap.parse_args()
    F = {k: Font(os.path.join(args.fonts, path), fam, wt) for k, (path, fam, wt) in FONT_FILES.items()}
    os.makedirs(args.out, exist_ok=True)
    outputs = {
        "header.svg": build_header(F),
        "now.svg": build_now(F),
        "card-phish-guard.svg": card_phish_guard(F),
        "card-pricewatch.svg": card_pricewatch(F),
        "card-cache-api.svg": card_cache_api(F),
        "card-social-analytics.svg": card_social(F),
        "stack.svg": build_stack(F),
        "footer.svg": build_footer(F),
    }
    for name, svg in outputs.items():
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"{name:28s} {len(svg.encode()) / 1024:7.1f} KB")


if __name__ == "__main__":
    main()
