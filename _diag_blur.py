"""
Diagnostic harness for the Lenovo Type-C charger false-positive blur case.

Synthesizes an image matching the measurable properties of the reported photo:
- dark black product (charger) in sharp focus, on a tan cardboard box with text
- green plant in a white pot (left)
- textured cream wall with horizontal brown slats (background, slightly soft)
- wooden floor (bottom), slightly soft

Then runs the REAL QualityCheckService._check_blur and dumps the vote breakdown
so we can see exactly which branch crosses the reject threshold.
"""
import numpy as np
import cv2
from PIL import Image
from quality_service import QualityCheckService


def _add_noise(img, sigma):
    n = np.random.normal(0, sigma, img.shape).astype(np.float32)
    return np.clip(img.astype(np.float32) + n, 0, 255).astype(np.uint8)


def build_scene(seed=0):
    """Build an RGB image (600x600) approximating the reported scene."""
    rng = np.random.default_rng(seed)
    H, W = 600, 600
    img = np.zeros((H, W, 3), dtype=np.uint8)

    # --- Background: cream wall (top ~60%) with horizontal brown slats ---
    wall = np.full((H, W, 3), (225, 218, 205), dtype=np.uint8)  # cream
    # horizontal brown slat stripes
    for y in (90, 200):
        cv2.rectangle(wall, (0, y), (W, y + 14), (120, 80, 55), -1)
    # wall texture (fine) — but SLIGHTLY soft (blurred) to mimic DoF
    wall = _add_noise(wall, 6)
    wall = cv2.GaussianBlur(wall, (5, 5), 1.2)  # mild bokeh
    img[:, :] = wall

    # --- Wooden floor (bottom ~30%) ---
    floor = np.full((H, W, 3), (150, 110, 70), dtype=np.uint8)
    floor = _add_noise(floor, 8)
    # plank lines
    for x in range(0, W, 70):
        cv2.line(floor, (x, 0), (x - 40, H), (110, 80, 50), 2)
    floor = cv2.GaussianBlur(floor, (5, 5), 1.3)
    img[int(H * 0.68):, :] = floor[int(H * 0.68):, :]

    # --- Cardboard box (center-bottom), tan, IN FOCUS with text ---
    bx0, by0, bx1, by1 = 150, 330, 560, 520
    cv2.rectangle(img, (bx0, by0), (bx1, by1), (175, 140, 95), -1)
    # box top face (lighter)
    pts = np.array([[bx0, by0], [bx1, by0], [bx1 - 30, by0 - 40], [bx0 - 30, by0 - 40]], np.int32)
    cv2.fillPoly(img, [pts], (195, 165, 120))
    # SHARP printed text "Lenovo Type-C" on the box front
    cv2.putText(img, "Lenovo Type-C", (bx0 + 40, by0 + 110),
                cv2.FONT_HERSHEY_SIMPLEX, 1.6, (40, 40, 45), 3, cv2.LINE_AA)
    # box edges (sharp)
    cv2.rectangle(img, (bx0, by0), (bx1, by1), (110, 85, 55), 2)

    # --- Black charger (center), dark, IN FOCUS ---
    # charger brick
    cv2.rectangle(img, (250, 150), (380, 300), (25, 25, 28), -1)
    cv2.rectangle(img, (250, 150), (380, 300), (60, 60, 65), 2)  # sharp rim highlight
    # yellow label sticker on charger
    cv2.rectangle(img, (270, 175), (340, 230), (210, 200, 60), -1)
    cv2.putText(img, "65W", (278, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2, cv2.LINE_AA)
    # coiled black cable (sharp curves)
    for r in (40, 55, 70):
        cv2.circle(img, (430, 250), r, (20, 20, 22), 6)
    # red-tipped USB-C connector
    cv2.rectangle(img, (300, 300), (330, 360), (30, 30, 32), -1)
    cv2.rectangle(img, (305, 300), (325, 312), (40, 40, 180), -1)  # red tip

    # --- Green plant in white pot (left) ---
    cv2.rectangle(img, (40, 230), (140, 340), (235, 235, 232), -1)  # white pot (sharp)
    cv2.rectangle(img, (40, 230), (140, 340), (180, 180, 178), 2)
    # leaves (sharp green)
    for (cx, cy, ang) in [(90, 180, -20), (75, 150, 10), (105, 160, 30), (90, 130, 0)]:
        cv2.ellipse(img, (cx, cy), (12, 55), ang, 0, 360, (40, 120, 50), -1)

    return Image.fromarray(img)


def soften(im, bg_sigma):
    """Apply a stronger global softening to mimic a real phone photo with DoF + JPEG."""
    a = np.array(im)
    a = cv2.GaussianBlur(a, (3, 3), bg_sigma)
    # JPEG round-trip to add realistic compression
    ok, enc = cv2.imencode('.jpg', cv2.cvtColor(a, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
    a = cv2.cvtColor(cv2.imdecode(enc, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    return Image.fromarray(a)


def build_realistic(seed=0):
    """
    More faithful to the real photo: the BACKGROUND (wall, floor, plant) is
    soft from depth-of-field, but the PRODUCT (charger, box text, cable) stays
    in sharp focus. Then a light global JPEG/blur is applied like a phone photo.
    """
    rng = np.random.default_rng(seed)
    H, W = 600, 600
    # Background layer — built then heavily softened
    bg = np.full((H, W, 3), (225, 218, 205), dtype=np.uint8)
    for y in (90, 200):
        cv2.rectangle(bg, (0, y), (W, y + 14), (120, 80, 55), -1)
    floor = np.full((H, W, 3), (150, 110, 70), dtype=np.uint8)
    for x in range(0, W, 70):
        cv2.line(floor, (x, 0), (x - 40, H), (110, 80, 50), 2)
    bg[int(H * 0.68):, :] = floor[int(H * 0.68):, :]
    bg = _add_noise(bg, 5)
    bg = cv2.GaussianBlur(bg, (13, 13), 5.0)  # strong DoF bokeh on background

    img = bg.copy()
    # Sharp foreground: box (mid-tone, moderate text contrast)
    bx0, by0, bx1, by1 = 150, 330, 560, 520
    cv2.rectangle(img, (bx0, by0), (bx1, by1), (170, 135, 92), -1)
    cv2.putText(img, "Lenovo Type-C", (bx0 + 40, by0 + 110),
                cv2.FONT_HERSHEY_SIMPLEX, 1.4, (55, 50, 50), 2, cv2.LINE_AA)
    cv2.rectangle(img, (bx0, by0), (bx1, by1), (120, 92, 60), 2)
    # charger — VERY DARK, low surface texture (the real product)
    cv2.rectangle(img, (250, 150), (390, 305), (22, 22, 25), -1)
    cv2.rectangle(img, (250, 150), (390, 305), (45, 45, 50), 1)  # faint rim
    # small yellow label (only sharp-ish detail on the dark product)
    cv2.rectangle(img, (272, 172), (330, 215), (180, 170, 55), -1)
    # coiled black cable (dark on dark, low contrast)
    for r in (40, 55, 70):
        cv2.circle(img, (440, 245), r, (18, 18, 20), 5)
    cv2.rectangle(img, (300, 300), (328, 358), (26, 26, 30), -1)
    # white pot + plant (sharp)
    cv2.rectangle(img, (40, 230), (140, 340), (232, 232, 228), -1)
    cv2.rectangle(img, (40, 230), (140, 340), (170, 170, 168), 2)
    for (cx, cy, ang) in [(90, 180, -20), (75, 150, 10), (105, 160, 30), (90, 130, 0)]:
        cv2.ellipse(img, (cx, cy), (12, 55), ang, 0, 360, (45, 115, 55), -1)
    # light global phone-photo softening + JPEG
    img = cv2.GaussianBlur(img, (3, 3), 0.8)
    ok, enc = cv2.imencode('.jpg', cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
    img = cv2.cvtColor(cv2.imdecode(enc, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    return Image.fromarray(img)


def build_glossy_reflection(dark_surface=True):
    """
    A genuine glossy-reflection DEFECT: sharp product sitting on a reflective
    surface that shows a softened MIRRORED copy below it. This MUST stay flagged
    (has_bottom_strip_blur=True). Tests the verifier's 'dark glossy reflection'
    counterexample.
    """
    H, W = 600, 600
    surf = 25 if dark_surface else 235
    img = np.full((H, W, 3), surf, dtype=np.uint8)
    # sharp product in upper area (band ~2-4)
    cv2.rectangle(img, (180, 120), (420, 300), (60, 60, 65), -1)
    cv2.putText(img, "PRODUCT", (200, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.4,
                (230, 230, 230), 3, cv2.LINE_AA)
    cv2.rectangle(img, (180, 120), (420, 300), (200, 200, 205), 3)
    # mirrored reflection below (softened copy), retains structure → real defect
    refl = img[120:300, 180:420].copy()
    refl = cv2.flip(refl, 0)
    refl = cv2.GaussianBlur(refl, (9, 9), 4.0)  # softened but STRUCTURED
    img[300:480, 180:420] = refl
    return Image.fromarray(img)


def build_blurry_with_sharp_band():
    """
    A genuinely OUT-OF-FOCUS product, but with ONE tack-sharp horizontal band
    (e.g. a barcode/packaging-text strip). The verifier warned a peak_lap-based
    override could let this pass. With has_sharp_subject keyed on the CENTER
    crop (not peak_lap), the blurry subject should still be caught.
    """
    H, W = 600, 600
    img = np.full((H, W, 3), 180, dtype=np.uint8)
    # blurry product filling center
    cv2.rectangle(img, (120, 120), (480, 480), (90, 90, 95), -1)
    cv2.putText(img, "Model XYZ 2024", (150, 320), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                (40, 40, 40), 2, cv2.LINE_AA)
    img = cv2.GaussianBlur(img, (15, 15), 7.0)  # whole thing out of focus
    # now stamp ONE razor-sharp thin barcode band near the bottom edge
    for x in range(60, 540, 6):
        cv2.line(img, (x, 520), (x, 545), (0, 0, 0), 2)
    return Image.fromarray(img)


def run():
    qcs = QualityCheckService()
    # Regression checks for verifier counterexamples
    print("### VERIFIER COUNTEREXAMPLE CHECKS ###")
    for nm, builder, must_pass in [
        ("glossy-reflection-DARK", lambda: build_glossy_reflection(True), False),
        ("glossy-reflection-WHITE", lambda: build_glossy_reflection(False), False),
        ("blurry+one-sharp-band", build_blurry_with_sharp_band, False),
    ]:
        r = qcs._check_blur(builder())
        dd = r["details"]
        ok = "OK" if r["passed"] == must_pass else "*** WRONG ***"
        print(f"  {nm}: PASSED={r['passed']} (want_pass={must_pass}) {ok} "
              f"conf={dd['blur_confidence']} has_strip={dd['has_bottom_strip_blur']} "
              f"strip_ratio={dd['bottom_strip_ratio']} center_lap={dd['center_lap_var']}")
    print()

    # Sweep increasing global softness + a realistic (sharp-product/soft-bg) case
    configs = [("sharp", 0.0), ("mild", 0.6),
               ("REALISTIC(sharp-prod/soft-bg)", -1),
               # genuinely blurry: EVERYTHING soft incl product → MUST FAIL
               ("BLURRY-g2.5", -10), ("BLURRY-g3.5", -2), ("BLURRY-g4.5", -11),
               ("BLURRY-extreme", -3)]
    expect = {"sharp": True, "mild": True, "REALISTIC(sharp-prod/soft-bg)": True,
              "BLURRY-g3.5": False, "BLURRY-g4.5": False, "BLURRY-extreme": False}
    for name, sig in configs:
        if sig == -1:
            im = build_realistic(0)
        elif sig == -10:
            im = soften(build_scene(0), 2.5)
        elif sig == -2:
            im = soften(build_scene(0), 3.5)   # whole image heavily blurred
        elif sig == -11:
            im = soften(build_scene(0), 4.5)
        elif sig == -3:
            a = np.array(build_scene(0))
            a = cv2.GaussianBlur(a, (15, 15), 6.0)
            im = Image.fromarray(a)
        else:
            im = build_scene(0)
            if sig > 0:
                im = soften(im, sig)
        res = qcs._check_blur(im)
        d = res["details"]
        exp = expect.get(name)
        ok = "OK" if (exp is None or res['passed'] == exp) else "*** WRONG ***"
        print("=" * 70)
        print(f"cfg={name}  PASSED={res['passed']} (expect_pass={exp}) {ok}  blur_conf={d['blur_confidence']}")
        print(f"  has_bright_background = {d['has_bright_background']}")
        print(f"  is_product_photo_layout = {d['is_product_photo_layout']}  patterns={d['layout_patterns']}")
        print(f"  laplacian_var={d['laplacian_var']} center_lap={d['center_lap_var']} roi_lap={d['roi_lap_var']} surface_lap={d['surface_lap_var']}")
        print(f"  best_lap_used={d['best_lap_used']}")
        print(f"  tenengrad={d['tenengrad_score']} freq_ratio={d['freq_ratio']}")
        print(f"  edge_density={d['edge_density']} center_edge_density={d['center_edge_density']}")
        print(f"  detail_loss={d['detail_loss']} image_has_texture={d['image_has_texture']}")
        print(f"  is_motion_blurred={d['is_motion_blurred']} motion_ind={d['motion_blur_indicator']}")
        print(f"  has_patch_blur={d['has_patch_blur']} frac={d['patch_blur_fraction']}")
        print(f"  has_bottom_strip_blur={d['has_bottom_strip_blur']} ratio={d['bottom_strip_ratio']} bottom_edge={d['bottom_edge_density']}")
        print(f"  top_half_lap={d['top_half_lap']} bottom_strip_lap={d['bottom_strip_lap']}")
        print(f"  absolute_reject={d['absolute_reject']}  snr={d['snr']}")
        print(f"  vote_breakdown={d['vote_breakdown']}")


if __name__ == "__main__":
    run()
