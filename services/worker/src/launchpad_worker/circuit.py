"""Five user-reference layouts, with real footage in every slide.

temp1: title/circuit cover; temp2: chapter side rails; temp3: text/media split;
temp4: visual + legend; temp5: tablet frame. Reference text and photos are not used.
Coordinates below use the references' 1600 x 900 design grid.
"""

from launchpad_api.settings import ROOT
from PIL import Image, ImageDraw, ImageFont

from .editorial import fit_text, items

KINDS = ("circuit-cover", "chapter-rails", "image-split", "legend-list", "tablet-demo")
SLOTS = (
    (100, 220, 1400, 530),
    (180, 240, 1240, 510),
    (390, 120, 1120, 625),
    (100, 210, 1090, 540),
    (110, 175, 1100, 570),
)
NAVY, ORANGE, PAPER, INK = "#232f3e", "#ff9900", "#dfe6ec", "#192b40"


def kind(index):
    return KINDS[index % len(KINDS)]


def layout(request, index=0):
    if request["orientation"] == "portrait":
        return (1080, 1920), (54, 450, 972, 1060)
    x, y, w, h = SLOTS[index % len(SLOTS)]
    return (2560, 1440), tuple(round(value * 1.6 / 2) * 2 for value in (x, y, w, h))


def content_scale(request):
    # Static browser reflow keeps text readable without animated camera zoom.
    if request.get("visual_style") == "cinematic":
        return 1.0
    return 1.15 if request["orientation"] == "portrait" else 1.4


def heading_font(size):
    face = ImageFont.truetype(str(ROOT / "assets" / "RobotoMono-Variable.ttf"), size)
    face.set_variation_by_axes([700])
    return face


def header_text(scene, index, brand):
    return brand if index == 0 else scene["title"]


def entries(scene):
    sentences = items(scene)
    return sentences[:2] + [" ".join(sentences[2:])] if len(sentences) > 3 else sentences


def legend_rows(scene, story_scenes=None):
    """Use reviewed storyboard copy, never manufacture extra feature claims."""
    if story_scenes and len(story_scenes) > 2:
        return [
            {"title": row["title"], "copy": row["on_screen_copy"], "source_ids": row["source_ids"]}
            for row in story_scenes[1:4]
        ]
    return [
        {"title": f"{n + 1:02d}", "copy": entry, "source_ids": scene.get("source_ids", [])}
        for n, entry in enumerate(entries(scene))
    ]


class Painter:
    def __init__(self, image):
        self.draw = ImageDraw.Draw(image)
        self.sx, self.sy = image.width / 1600, image.height / 900

    def point(self, p):
        return (round(p[0] * self.sx), round(p[1] * self.sy))

    def box(self, rect):
        x, y, w, h = rect
        return (*self.point((x, y)), *self.point((x + w, y + h)))

    def polygon(self, points, color):
        self.draw.polygon([self.point(p) for p in points], fill=color)

    def line(self, points, color, width=1):
        self.draw.line(
            [self.point(p) for p in points],
            fill=color,
            width=max(1, round(width * self.sx)),
            joint="curve",
        )

    def rect(self, rect, color, radius=0, outline=None, width=1):
        self.draw.rounded_rectangle(
            self.box(rect),
            radius=round(radius * self.sx),
            fill=color,
            outline=outline,
            width=max(1, round(width * self.sx)),
        )

    def text(self, text, rect, face, size, color=INK, minimum=18):
        x, y, w, h = rect
        fit_text(
            self.draw,
            text,
            (*self.point((x, y)), round(w * self.sx), round(h * self.sy)),
            face,
            size=round(size * self.sx),
            minimum=round(min(size, minimum) * self.sx),
            color=color,
        )


def circuit_frame(p, selected):
    # Cut-corner outer frame and slim circuit traces match the supplied references.
    p.polygon([(32, 26), (1530, 26), (1568, 64), (1568, 874), (32, 874)], PAPER)
    p.line(
        [(58, 205), (58, 111), (108, 61), (150, 61), (176, 83), (246, 83), (281, 49), (365, 49)],
        "#b7c3ce",
        1.5,
    )
    p.line([(58, 109), (58, 254)], ORANGE, 3)
    p.line(
        [
            (1232, 48),
            (1320, 48),
            (1360, 80),
            (1430, 80),
            (1460, 53),
            (1490, 53),
            (1538, 103),
            (1538, 254),
        ],
        "#9cacbd",
        1.5,
    )
    p.line([(1538, 112), (1538, 251)], ORANGE, 3)
    for n in range(3):
        x = 1260 + n * 63
        p.line(
            [(x, 28), (x, 110 + n * 20), (x + 28, 138 + n * 20), (x + 28, 174 + n * 24)], "#dce1e6"
        )
        cx, cy = x + 28, 174 + n * 24
        p.rect((cx - 2, cy - 2, 4, 4), PAPER, 2, "#bdc7d1")

    if selected == "chapter-rails":
        for right in (False, True):

            def mirror(points, right=right):
                return [(1600 - x if right else x, y) for x, y in points]

            p.polygon(
                mirror(
                    [
                        (0, 54),
                        (106, 54),
                        (152, 110),
                        (152, 275),
                        (122, 307),
                        (122, 588),
                        (152, 626),
                        (152, 795),
                        (108, 848),
                        (0, 848),
                    ]
                ),
                "#344e69",
            )
            for y in range(100, 820, 58):
                p.line(mirror([(0, y), (106, y), (138, y + 26)]), "#60768d")
            for x in (26, 72):
                p.line(mirror([(x, 64), (x, 824)]), "#60768d")
            p.line(mirror([(122, 319), (122, 581)]), ORANGE, 5)
    else:
        p.polygon(
            [
                (0, 690),
                (55, 690),
                (102, 735),
                (156, 735),
                (248, 823),
                (387, 823),
                (445, 900),
                (0, 900),
            ],
            "#344e69",
        )
        p.polygon([(0, 745), (40, 745), (182, 900), (86, 900)], "#ff9900")
        p.polygon([(190, 869), (339, 869), (373, 900), (224, 900)], "#71869a")
        for y in (754, 783, 812, 841):
            p.line([(6, y), (82, y), (118, y + 32), (211, y + 32)], "#71869a")
        p.line([(302, 850), (620, 850), (666, 815), (734, 815)], "#b8c5d0")
        if selected in ("legend-list", "tablet-demo"):
            p.polygon(
                [
                    (854, 26),
                    (1308, 26),
                    (1284, 59),
                    (1218, 59),
                    (1194, 91),
                    (974, 91),
                    (948, 59),
                    (880, 59),
                ],
                "#344e69",
            )
            p.line([(982, 80), (1190, 80)], ORANGE, 3)
        if selected == "tablet-demo":
            p.polygon(
                [(1440, 815), (1480, 815), (1510, 786), (1600, 786), (1600, 900), (1340, 900)],
                "#344e69",
            )
            p.polygon([(1530, 824), (1600, 824), (1600, 862), (1490, 900), (1450, 900)], ORANGE)


def video_frame(draw, aperture, scale):
    """Slide 5's rounded shell, navy bezel and side button, for every aperture."""
    x, y, w, h = aperture

    def rect(bounds, radius, color):
        draw.rounded_rectangle(tuple(round(v) for v in bounds), radius=round(radius), fill=color)

    rect(
        (x - 25 * scale, y - 26 * scale, x + w + 30 * scale, y + h + 27 * scale),
        26 * scale,
        "#e0e4e8",
    )
    rect((x - 11 * scale, y - 11 * scale, x + w + 11 * scale, y + h + 11 * scale), 22 * scale, NAVY)
    rect(
        (x + w + 17 * scale, y + h / 2 - 44 * scale, x + w + 23 * scale, y + h / 2 + 44 * scale),
        3 * scale,
        "#a0abb6",
    )
    draw.rounded_rectangle(
        (x - 3, y - 3, x + w + 3, y + h + 3), radius=39, outline="#677b90", width=3
    )


def draw_slide(scene, request, index, total, path, body_font, brand, story_scenes=None):
    size, aperture = layout(request, index)
    selected = kind(index)
    image = Image.new("RGB", size, NAVY)
    p = Painter(image)
    circuit_frame(p, selected)
    video_frame(p.draw, aperture, 0.75 if request["orientation"] == "portrait" else 1.6)
    title = header_text(scene, index, brand).upper()
    copy = scene["on_screen_copy"]
    if request["orientation"] == "portrait":
        # Reflow the reference's content instead of shrinking a desktop slide.
        draw = p.draw
        fit_text(draw, title, (82, 152, 896, 140), heading_font, size=64, color=INK)
        fit_text(draw, copy, (82, 314, 896, 102), body_font, size=34, color=INK)
        if request.get("captions"):
            draw.rounded_rectangle((44, 1538, 1036, 1700), radius=28, fill=NAVY)
    elif selected == "circuit-cover":
        p.text(title, (104, 92, 1375, 65), heading_font, 58, ORANGE if index == 0 else INK)
        p.text(copy, (106, 163, 1370, 28), body_font, 25)
    elif selected == "chapter-rails":
        p.rect((184, 110, 110, 92), PAPER, 12, ORANGE, 2)
        p.text(f"{index + 1:02d}", (203, 118, 90, 75), heading_font, 60, ORANGE)
        p.text(title, (322, 105, 1080, 76), heading_font, 49)
        p.text(copy, (324, 180, 1080, 30), body_font, 25)
    elif selected == "image-split":
        p.text(title, (92, 218, 260, 230), heading_font, 38)
        p.text(copy, (94, 484, 260, 222), body_font, 25)
    elif selected == "legend-list":
        p.text(title, (104, 100, 1395, 74), heading_font, 49)
        rows = legend_rows(scene, story_scenes)
        spacing = 175 if len(rows) == 3 else 220
        for n, entry in enumerate(rows):
            y = 218 + n * spacing
            colors = (ORANGE, "#748ba3", NAVY)
            p.rect((1230, y + 5, 22, 22), colors[n], 5)
            p.text(entry["title"].upper(), (1268, y, 244, 60), heading_font, 24)
            p.text(entry["copy"], (1268, y + 66, 244, spacing - 76), body_font, 23, minimum=18)
    else:
        p.text(title, (1270, 234, 240, 210), heading_font, 36)
        p.text(copy, (1270, 490, 240, 230), body_font, 25)

    if request["orientation"] != "portrait":
        if request.get("captions"):
            p.rect((240, 780, 1120, 66), NAVY, 18)
        # A discreet scene counter; repeating product-name footers are omitted.
        p.text(f"{index + 1:02d} / {total:02d}", (1390, 770, 140, 30), heading_font, 17, INK)
    image.save(path)
