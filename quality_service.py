"""
OpenCV Quality Check Service
Step 1 in the pipeline: Image quality validation
"""

import cv2
import numpy as np
from PIL import Image
from typing import Dict, Tuple


class QualityCheckService:
    def __init__(self):
        """Initialize quality check thresholds"""
        self.min_resolution = 100  # minimum width/height (allows 400x400 and up)
        self.max_resolution = 10000  # maximum width/height
        self.min_aspect_ratio = 0.2  # 1:5
        self.max_aspect_ratio = 5.0  # 5:1
        self.blur_threshold = 150  # Laplacian variance threshold (stricter - catches slight blur)
        self.min_filesize = 1024  # 1KB minimum
        
        print("Quality Check Service initialized")
    
    def preprocess_image(self, image: Image.Image, enhance: bool = True) -> Image.Image:
        """
        Preprocess image for better detection
        - Contrast enhancement
        - Sharpening
        - Noise reduction
        """
        if not enhance:
            return image
        
        img_array = np.array(image)
        
        # Convert to LAB color space for better contrast adjustment
        if len(img_array.shape) == 3:
            lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to L channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)
            
            # Merge channels back
            lab_enhanced = cv2.merge([l_enhanced, a, b])
            enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
        else:
            # Grayscale image
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(img_array)
        
        # Sharpen the image
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # Denoise slightly (preserve edges)
        if len(sharpened.shape) == 3:
            denoised = cv2.fastNlMeansDenoisingColored(sharpened, None, 10, 10, 7, 21)
        else:
            denoised = cv2.fastNlMeansDenoising(sharpened, None, 10, 7, 21)
        
        return Image.fromarray(denoised)
    
    def check_image(self, image: Image.Image, file_size: int = None) -> Dict:
        """
        Comprehensive image quality check with confidence scores
        
        Returns:
            Dict with pass/fail status, confidence scores, and reasons
        """
        checks = {
            "resolution": self._check_resolution(image),
            "aspect_ratio": self._check_aspect_ratio(image),
            "blur": self._check_blur(image),
            "corrupted": self._check_corrupted(image),
            "screenshot_ui": self._check_screenshot_ui(image)
        }
        
        # Extract confidence scores (0.0 to 1.0)
        screenshot_confidence = checks["screenshot_ui"].get("confidence", 0.0)
        blur_confidence = checks["blur"].get("confidence", 0.0)
        
        # Hard rule: OpenCV screenshot detection is FINAL - only flag clear mobile UI
        opencv_block = screenshot_confidence > 0.90
        
        # Determine overall pass/fail
        failed_checks = [name for name, result in checks.items() if not result["passed"]]
        passed = len(failed_checks) == 0 and not opencv_block
        
        return {
            "passed": passed,
            "checks": checks,
            "failed_checks": failed_checks,
            "action": "BLOCK" if opencv_block else ("PASS" if passed else "BLOCK"),
            "reason": "Screenshot detected by OpenCV" if opencv_block else (", ".join(failed_checks) if failed_checks else "All quality checks passed"),
            "opencv_risk": screenshot_confidence * 0.7 + blur_confidence * 0.3,
            "screenshot_confidence": screenshot_confidence,
            "blur_confidence": blur_confidence
        }
    
    def _check_resolution(self, image: Image.Image) -> Dict:
        """Check if image resolution is within acceptable range"""
        width, height = image.size
        
        # Check minimum resolution
        if width < self.min_resolution or height < self.min_resolution:
            return {
                "passed": False,
                "reason": f"Resolution too low: {width}x{height}",
                "details": {"width": width, "height": height}
            }
        
        # Check maximum resolution
        if width > self.max_resolution or height > self.max_resolution:
            return {
                "passed": False,
                "reason": f"Resolution too high: {width}x{height}",
                "details": {"width": width, "height": height}
            }
        
        return {
            "passed": True,
            "reason": "Resolution acceptable",
            "details": {"width": width, "height": height}
        }
    
    def _check_aspect_ratio(self, image: Image.Image) -> Dict:
        """Check if aspect ratio is reasonable"""
        width, height = image.size
        aspect_ratio = width / height if height > 0 else 0
        
        if aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
            return {
                "passed": False,
                "reason": f"Unusual aspect ratio: {aspect_ratio:.2f}",
                "details": {"aspect_ratio": aspect_ratio}
            }
        
        return {
            "passed": True,
            "reason": "Aspect ratio acceptable",
            "details": {"aspect_ratio": aspect_ratio}
        }
    
    def _check_blur(self, image: Image.Image) -> Dict:
        """
        Blur detection using a soft confidence-voting system.

        Design principles:
        - No single metric causes rejection (hard_reject removed).
        - detail_loss is only trusted when the image has texture to measure.
        - Motion blur is only flagged when anisotropy AND low sharpness agree.
        - Laplacian penalty tiers start at realistic thresholds for product photos.
        - Sharpness is measured on the center crop (where the product lives) in
          addition to the global image, preventing white/plain borders from
          diluting the signal.
        """
        img_array = np.array(image.convert('L'))
        h_img, w_img = img_array.shape

        # ── 1. GLOBAL METRICS ────────────────────────────────────────────────

        # Laplacian variance — the primary sharpness signal
        laplacian = cv2.Laplacian(img_array, cv2.CV_64F)
        laplacian_var = laplacian.var()
        laplacian_mean = np.abs(laplacian).mean()

        # Tenengrad (Sobel gradient energy) — reliable, content-independent
        gx = cv2.Sobel(img_array, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(img_array, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gx**2 + gy**2)
        tenengrad_score = np.mean(gradient_magnitude**2)
        gradient_std = np.std(gradient_magnitude)

        # FFT high-frequency energy ratio
        fft_shift = np.fft.fftshift(np.fft.fft2(img_array))
        magnitude_spectrum = np.abs(fft_shift)
        fh, fw = magnitude_spectrum.shape
        cy, cx = fh // 2, fw // 2
        radius = min(fh, fw) // 4
        yy, xx = np.ogrid[:fh, :fw]
        dist_sq = (xx - cx)**2 + (yy - cy)**2
        mask_high = dist_sq > radius**2
        mask_mid  = (dist_sq > (radius // 2)**2) & ~mask_high
        high_freq_energy = np.mean(magnitude_spectrum[mask_high])
        mid_freq_energy  = np.mean(magnitude_spectrum[mask_mid])
        freq_ratio = high_freq_energy / (mid_freq_energy + 1e-10)

        # Edge density (Canny)
        edges = cv2.Canny(img_array, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        strong_edges = cv2.Canny(img_array, 100, 200)
        strong_edge_density = np.sum(strong_edges > 0) / strong_edges.size
        edge_strength_ratio = strong_edge_density / (edge_density + 1e-10)

        # ── 2. CENTER-CROP METRICS ───────────────────────────────────────────
        # Products live in the center. Measure sharpness there rather than
        # letting plain borders drag the global score down.
        cy_img, cx_img = h_img // 2, w_img // 2
        crop_h = max(1, int(h_img * 0.6))
        crop_w = max(1, int(w_img * 0.6))
        y1 = cy_img - crop_h // 2
        x1 = cx_img - crop_w // 2
        center_crop = img_array[y1:y1+crop_h, x1:x1+crop_w]

        center_lap_var = cv2.Laplacian(center_crop, cv2.CV_64F).var()
        center_edges_arr = cv2.Canny(center_crop, 50, 150)
        center_edge_density = np.sum(center_edges_arr > 0) / center_edges_arr.size

        # ── 2b. PRODUCT-ROI METRICS (white-background fix) ───────────────────
        # On studio/white-bg images the flat white background inflates the
        # global Laplacian, masking an actually-blurry product.  We measure
        # sharpness only over non-white product pixels.
        #
        # Strategy: build a foreground mask (pixels ≤ 230), erode slightly to
        # strip anti-aliased edges, then compute Laplacian variance only there.
        # Fall back to center_lap_var when the mask is too small to be reliable.
        WHITE_THRESH = 230
        product_mask = (img_array <= WHITE_THRESH).astype(np.uint8)
        product_pixel_count = int(product_mask.sum())
        roi_lap_var = center_lap_var  # safe default

        if product_pixel_count > (h_img * w_img * 0.05):  # at least 5% non-white
            # Erode 3 px to remove background fringe pixels
            kernel_erode = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            product_mask_eroded = cv2.erode(product_mask, kernel_erode, iterations=2)
            roi_pixels = product_pixel_count  # use un-eroded count for ratio

            # Laplacian of full image, sampled only over product mask
            lap_full = cv2.Laplacian(img_array, cv2.CV_64F)
            masked_values = lap_full[product_mask_eroded > 0]
            if masked_values.size > 200:  # enough pixels for a stable estimate
                roi_lap_var = float(np.var(masked_values))

        # bright-background flag — used to decide which variance to trust
        corners_gray_brightness = [
            img_array[:h_img // 8, :w_img // 8],
            img_array[:h_img // 8, -w_img // 8:],
            img_array[-h_img // 8:, :w_img // 8],
            img_array[-h_img // 8:, -w_img // 8:],
        ]
        avg_corner_brightness_blur = float(np.mean([c.mean() for c in corners_gray_brightness]))
        has_bright_background = avg_corner_brightness_blur > 200

        # ── 3. PRODUCT LAYOUT DETECTION ──────────────────────────────────────
        # Broadened: OR-logic so any of the three patterns qualify.
        y_start, y_end = h_img // 4, 3 * h_img // 4
        x_start, x_end = w_img // 4, 3 * w_img // 4
        zone_center = edges[y_start:y_end, x_start:x_end]
        zone_border = np.concatenate([
            edges[:h_img//4, :].ravel(),
            edges[3*h_img//4:, :].ravel(),
            edges[:, :w_img//4].ravel(),
            edges[:, 3*w_img//4:].ravel(),
        ])
        center_edge_density_zone = np.sum(zone_center > 0) / (zone_center.size + 1e-10)
        border_edge_density_zone  = np.sum(zone_border > 0) / (zone_border.size + 1e-10)

        # Pattern A: classic white-background centered product
        pattern_centered = (
            center_edge_density_zone > (border_edge_density_zone * 1.8)
            and center_edge_density_zone > 0.04
        )
        # Pattern B: product fills the frame (distributed edges everywhere)
        pattern_filled_frame = edge_density > 0.06 and center_edge_density > 0.05
        # Pattern C: uniform bright background (white/light-grey studio shot)
        corners_gray = [
            img_array[:h_img//8, :w_img//8],
            img_array[:h_img//8, -w_img//8:],
            img_array[-h_img//8:, :w_img//8],
            img_array[-h_img//8:, -w_img//8:],
        ]
        corner_means = [np.mean(c) for c in corners_gray]
        avg_corner_brightness = np.mean(corner_means)
        corner_std = np.std(corner_means)
        pattern_studio_bg = avg_corner_brightness > 170 and corner_std < 35

        is_product_photo_layout = pattern_centered or pattern_filled_frame or pattern_studio_bg

        # ── 3b. PATCH / SELECTIVE BLUR DETECTION ─────────────────────────────
        # Detects images where only certain rectangular regions are blurred
        # (e.g. face anonymisation, censored content) while background is sharp.
        # Global metrics miss this because the sharp background dominates.
        #
        # Method: evaluate both a 6×6 and 8×8 grid so smaller blur-masked
        # regions (like anonymized faces) still register even when they only
        # occupy part of a larger cell.
        patch_blur_fraction = 0.0
        has_patch_blur = False
        for GRID_ROWS, GRID_COLS in ((6, 6), (8, 8)):
            cell_h = max(1, h_img // GRID_ROWS)
            cell_w = max(1, w_img // GRID_COLS)
            cell_vars = []
            for gr in range(GRID_ROWS):
                for gc in range(GRID_COLS):
                    r0, r1 = gr * cell_h, min((gr + 1) * cell_h, h_img)
                    c0, c1 = gc * cell_w, min((gc + 1) * cell_w, w_img)
                    cell = img_array[r0:r1, c0:c1]
                    if cell.size > 0:
                        cell_vars.append(float(cv2.Laplacian(cell, cv2.CV_64F).var()))

            if len(cell_vars) < 4:
                continue

            median_cell_var = float(np.median(cell_vars))
            max_cell_var    = float(np.max(cell_vars))
            # A cell is "blurry" when its variance is far below the median AND
            # the median itself indicates some cells are genuinely sharp (> 50).
            if median_cell_var > 50 and max_cell_var > 200:
                blurry_threshold = median_cell_var * 0.25
                hard_blur_threshold = median_cell_var * 0.08  # near-zero = clearly blurred
                n_blurry = sum(1 for v in cell_vars if v < blurry_threshold)
                n_hard_blurry = sum(1 for v in cell_vars if v < hard_blur_threshold)
                current_fraction = n_blurry / len(cell_vars)
                patch_blur_fraction = max(patch_blur_fraction, current_fraction)
                # Two-tier trigger:
                # Tier A: a meaningful fraction of cells are blurry.
                # Tier B: a few cells are near-zero blurry, which is enough for
                #         face anonymisation or other selective blur overlays.
                has_patch_blur = has_patch_blur or (current_fraction >= 0.20) or (n_hard_blurry >= 3)

        # ── 4. DETAIL-LOSS (only meaningful when the image has texture) ───────
        blur_3x3 = cv2.GaussianBlur(img_array, (3, 3), 0)
        blur_5x5 = cv2.GaussianBlur(img_array, (5, 5), 0)
        blur_7x7 = cv2.GaussianBlur(img_array, (7, 7), 0)
        detail_loss_3x3 = np.mean(np.abs(img_array.astype(np.float32) - blur_3x3.astype(np.float32)))
        detail_loss_5x5 = np.mean(np.abs(img_array.astype(np.float32) - blur_5x5.astype(np.float32)))
        detail_loss_7x7 = np.mean(np.abs(img_array.astype(np.float32) - blur_7x7.astype(np.float32)))

        # detail_loss is only a blur signal when the image has enough texture
        # to lose. On a smooth surface a 3×3 blur removes almost nothing even
        # when the image is perfectly sharp — so we gate on edge_density.
        image_has_texture = edge_density > 0.05

        # DoG wavelet energy
        dog_1 = cv2.GaussianBlur(img_array, (3, 3), 0.5) - cv2.GaussianBlur(img_array, (3, 3), 1.0)
        dog_2 = cv2.GaussianBlur(img_array, (5, 5), 1.0) - cv2.GaussianBlur(img_array, (5, 5), 2.0)
        wavelet_energy = np.mean(np.abs(dog_1)) + np.mean(np.abs(dog_2))

        # ── 5. MOTION BLUR (anisotropy guard) ────────────────────────────────
        # The old metric measures directional texture, not motion blur.
        # We require BOTH anisotropy AND low sharpness to flag it.
        kernel_h = np.ones((1, 9)) / 9
        kernel_v = np.ones((9, 1)) / 9
        h_response = np.std(cv2.filter2D(img_array.astype(np.float32), -1, kernel_h))
        v_response = np.std(cv2.filter2D(img_array.astype(np.float32), -1, kernel_v))
        motion_blur_indicator = min(h_response, v_response) / (max(h_response, v_response) + 1e-10)
        # Only flag as motion-blurred when the ratio is very asymmetric (< 0.50,
        # was 0.70) AND the image is genuinely soft — avoids directional textures
        # like wood grain, fabric weave, corrugated packaging.
        is_motion_blurred = (motion_blur_indicator < 0.50 and laplacian_var < 300)

        # ── 6. NOISE METRICS ─────────────────────────────────────────────────
        kernel_size = 5
        mean_filtered = cv2.blur(img_array.astype(np.float32), (kernel_size, kernel_size))
        variance_map  = cv2.blur((img_array.astype(np.float32) - mean_filtered)**2,
                                  (kernel_size, kernel_size))
        noise_score   = np.mean(variance_map)
        blurred_5     = cv2.GaussianBlur(img_array, (5, 5), 0)
        high_freq_noise = np.mean(np.abs(img_array.astype(np.float32) - blurred_5.astype(np.float32)))
        signal_strength = np.std(mean_filtered)
        noise_strength  = np.mean(np.sqrt(variance_map))
        snr = signal_strength / (noise_strength + 1e-10)
        kernel_3x3 = np.ones((3, 3)) / 9
        local_mean = cv2.filter2D(img_array.astype(np.float32), -1, kernel_3x3)
        local_variance = cv2.filter2D((img_array.astype(np.float32) - local_mean)**2, -1, kernel_3x3)
        texture_consistency = np.std(local_variance)

        is_noisy = (
            noise_score > 250 or
            high_freq_noise > 13 or
            snr < 2.5 or
            (texture_consistency > 1400 and noise_score > 200)
        )

        # ── 7. CONTRAST ───────────────────────────────────────────────────────
        contrast = np.std(img_array)
        dynamic_range = int(np.max(img_array)) - int(np.min(img_array))

        # ── 8. SOFT CONFIDENCE VOTING ─────────────────────────────────────────
        # Each metric casts a weighted blur-confidence vote in [0, 1].
        # No single vote causes rejection. Weights sum to 1.0.
        votes = []

        # (a) Laplacian — use the best available estimate:
        #   • bright background (studio shot): prefer product-ROI variance so the
        #     flat white area doesn't inflate the signal and mask product blur
        #   • otherwise: use the better of global and center-crop
        if has_bright_background:
            best_lap = max(roi_lap_var, center_lap_var)
        else:
            best_lap = max(laplacian_var, center_lap_var, roi_lap_var)
        lap_conf = max(0.0, 1.0 - best_lap / 500.0)   # saturates at 0 for lap >= 500 (was 800)
        votes.append(lap_conf * 0.28)

        # (b) Tenengrad — content-independent, reliable
        ten_conf = max(0.0, 1.0 - tenengrad_score / 1200.0)   # saturates at 0 for ten >= 1200 (was 2000)
        votes.append(ten_conf * 0.22)

        # (c) FFT frequency ratio
        fft_conf = max(0.0, 1.0 - freq_ratio / 0.6)
        votes.append(fft_conf * 0.15)

        # (d) detail_loss — only contributes when image has texture to lose
        if image_has_texture:
            dl_conf = max(0.0, 1.0 - detail_loss_3x3 / 5.0)
            votes.append(dl_conf * 0.15)
        else:
            # Redistribute weight to tenengrad so totals stay balanced
            ten_bonus = max(0.0, 1.0 - tenengrad_score / 2000.0)
            votes.append(ten_bonus * 0.15)

        # (e) Edge density — sparse edges in center suggests blur
        edge_conf = max(0.0, 1.0 - center_edge_density / 0.06)   # tighter cap (was 0.08)
        votes.append(edge_conf * 0.10)

        # (f) Motion blur — only when anisotropy + low sharpness agree
        if is_motion_blurred:
            votes.append(0.70 * 0.10)
        else:
            votes.append(0.0)

        # (g) Patch / selective blur — face anonymisation, censored regions.
        # Strong signal: counts as a hard boost when ≥25% of cells are blurry.
        # Weight is 0.30 so even a modest fraction pushes confidence above threshold.
        if has_patch_blur:
            votes.append(min(patch_blur_fraction * 1.20, 1.0) * 0.30)
        else:
            votes.append(0.0)

        blur_confidence = sum(votes)  # 0.0 = sharp, 1.0 = blurry

        # Product layout gives a grace margin: confirmed product photos need a
        # stronger signal before we reject.
        # Do NOT apply the grace margin when selective/patch blur is the trigger —
        # face-blur on a product background is never an acceptable product image.
        if is_product_photo_layout and not has_patch_blur:
            blur_confidence *= 0.88

        # ── 9. THRESHOLDS ────────────────────────────────────────────────────
        # Calibrated so obviously blurry phone-camera shots score > 0.65 and
        # sharp white-background product photos score < 0.45.
        REJECT_THRESHOLD    = 0.65   # was effectively ~0.40 with hard_reject
        BORDERLINE_THRESHOLD = 0.50

        is_blurry    = blur_confidence >= REJECT_THRESHOLD
        is_borderline = BORDERLINE_THRESHOLD <= blur_confidence < REJECT_THRESHOLD

        # ── 10. ABSOLUTE FLOOR — only truly catastrophic images ───────────────
        # These conditions are undeniable regardless of content type.
        # Kept minimal on purpose: a single clear signal that cannot be a
        # false positive for any legitimate product image.
        absolute_reject = (
            laplacian_var < 30 and center_lap_var < 30 and roi_lap_var < 30
        ) or (
            snr < 1.5                                       # signal buried in noise
        ) or (
            # Clearly blurry: all three lap measures below 80 AND tenengrad is low
            laplacian_var < 80 and center_lap_var < 80 and roi_lap_var < 80
            and tenengrad_score < 400
        )
        if absolute_reject:
            blur_confidence = 1.0
            is_blurry = True

        # ── 11. REASON STRING ────────────────────────────────────────────────
        quality_issues = []
        if snr < 2.5:
            quality_issues.append("extremely poor signal quality")
        elif snr < 5:
            quality_issues.append("poor signal quality")
        if is_motion_blurred:
            quality_issues.append("motion blur detected")
        if has_patch_blur:
            quality_issues.append(f"selective blur on {int(patch_blur_fraction*100)}% of image regions")
        # Use ROI-aware lap value for human-readable thresholds
        _lap_for_reason = roi_lap_var if has_bright_background else laplacian_var
        if _lap_for_reason < 50:
            quality_issues.append("extremely blurry")
        elif _lap_for_reason < 150:
            quality_issues.append("severely blurry")
        elif _lap_for_reason < 300:
            quality_issues.append("very blurry")
        if is_noisy:
            quality_issues.append("noisy/grainy")
        if image_has_texture and detail_loss_3x3 < 1.0:
            quality_issues.append("lacks detail")
        if contrast < 20:
            quality_issues.append("low contrast")
        quality_issue = " and ".join(quality_issues) if quality_issues else "poor quality"

        details = {
            "combined_score": round((1.0 - blur_confidence) * 100, 1),
            "blur_confidence": round(blur_confidence, 3),
            "is_product_photo_layout": is_product_photo_layout,
            "layout_patterns": {
                "centered": pattern_centered,
                "filled_frame": pattern_filled_frame,
                "studio_bg": pattern_studio_bg,
            },
            "center_edge_density": round(center_edge_density, 4),
            "border_edge_density": round(border_edge_density_zone, 4),
            "laplacian_var": round(laplacian_var, 2),
            "center_lap_var": round(center_lap_var, 2),
            "roi_lap_var": round(roi_lap_var, 2),
            "has_bright_background": has_bright_background,
            "best_lap_used": round(best_lap, 2),
            "has_patch_blur": has_patch_blur,
            "patch_blur_fraction": round(patch_blur_fraction, 3),
            "laplacian_mean": round(laplacian_mean, 3),
            "tenengrad_score": round(tenengrad_score, 2),
            "gradient_std": round(gradient_std, 3),
            "high_freq_energy": round(high_freq_energy, 3),
            "freq_ratio": round(freq_ratio, 4),
            "edge_density": round(edge_density, 4),
            "strong_edge_density": round(strong_edge_density, 4),
            "edge_strength_ratio": round(edge_strength_ratio, 4),
            "detail_loss": round(detail_loss_3x3, 3),
            "detail_loss_5x5": round(detail_loss_5x5, 3),
            "detail_loss_7x7": round(detail_loss_7x7, 3),
            "image_has_texture": image_has_texture,
            "wavelet_energy": round(wavelet_energy, 3),
            "motion_blur_indicator": round(motion_blur_indicator, 4),
            "is_motion_blurred": is_motion_blurred,
            "noise_score": round(noise_score, 3),
            "high_freq_noise": round(high_freq_noise, 3),
            "snr": round(snr, 3),
            "texture_consistency": round(texture_consistency, 3),
            "contrast": round(contrast, 3),
            "dynamic_range": dynamic_range,
            "is_noisy": is_noisy,
            "absolute_reject": absolute_reject,
            "vote_breakdown": {
                "laplacian": round(lap_conf, 3),
                "tenengrad": round(ten_conf, 3),
                "fft": round(fft_conf, 3),
                "motion_blur": float(is_motion_blurred),
            },
            "quality_grade": "poor" if is_blurry else "borderline" if is_borderline else "good",
            "confidence": round(blur_confidence, 3),
        }

        if is_blurry:
            reason_text = f"Image too {quality_issue} (blur_conf: {blur_confidence:.2f})"
            if is_product_photo_layout:
                reason_text += " [Product layout applied]"
            return {
                "passed": False,
                "reason": reason_text,
                "details": details,
                "confidence": round(blur_confidence, 3),
            }

        reason_text = f"Image sharpness acceptable (blur_conf: {blur_confidence:.2f})"
        if is_product_photo_layout:
            reason_text += " [Product layout]"
        return {
            "passed": True,
            "reason": reason_text,
            "details": details,
            "confidence": round(blur_confidence, 3),
        }
    
    def _check_corrupted(self, image: Image.Image) -> Dict:
        """Check if image appears corrupted"""
        try:
            # Try to get pixel data
            img_array = np.array(image)
            
            # Check for valid data
            if img_array.size == 0:
                return {
                    "passed": False,
                    "reason": "Image has no data",
                    "details": {}
                }
            
            # Check for unusual patterns (all same color, etc.)
            if len(img_array.shape) >= 2:
                std_dev = np.std(img_array)
                if std_dev < 1.0:  # Nearly uniform color
                    return {
                        "passed": False,
                        "reason": "Image appears corrupted (uniform color)",
                        "details": {"std_dev": std_dev}
                    }
            
            return {
                "passed": True,
                "reason": "Image not corrupted",
                "details": {}
            }
        
        except Exception as e:
            return {
                "passed": False,
                "reason": f"Image corrupted: {str(e)}",
                "details": {"error": str(e)}
            }
    
    def _check_screenshot_ui(self, image: Image.Image) -> Dict:
        """Check if image is a MOBILE PHONE screenshot by detecting status bar + navbar UI elements"""
        img_array = np.array(image)
        height, width = img_array.shape[:2]
        
        # Convert to grayscale
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # === 0. ENHANCED PRODUCT PHOTO DETECTION ===
        # Calculate background uniformity - product photos typically have plain backgrounds
        blur = cv2.GaussianBlur(gray, (21, 21), 0)
        background_variance = np.var(blur)
        
        # Check corners for white/uniform background
        corner_size = int(min(height, width) * 0.1)
        corners = [
            gray[0:corner_size, 0:corner_size],  # Top-left
            gray[0:corner_size, -corner_size:],  # Top-right
            gray[-corner_size:, 0:corner_size],  # Bottom-left
            gray[-corner_size:, -corner_size:]   # Bottom-right
        ]
        corner_means = [np.mean(c) for c in corners]
        corner_std = np.std(corner_means)
        avg_corner_brightness = np.mean(corner_means)
        
        # Check for centered product (common in product photography)
        center_region = gray[height//4:3*height//4, width//4:3*width//4]
        center_mean = np.mean(center_region)
        border_mean = np.mean([np.mean(gray[:height//4, :]), np.mean(gray[3*height//4:, :]),
                              np.mean(gray[:, :width//4]), np.mean(gray[:, 3*width//4:])])
        
        # Check if center is significantly different from borders (product vs background)
        center_vs_border_diff = abs(center_mean - border_mean)
        
        # Product photo indicators: white/uniform corners OR centered product with plain background
        is_likely_product_photo = (
            (avg_corner_brightness > 190 and corner_std < 20 and background_variance < 2500) or
            (avg_corner_brightness > 180 and corner_std < 30 and background_variance < 3500) or
            (center_vs_border_diff > 40 and avg_corner_brightness > 170 and corner_std < 40) or
            (background_variance < 1800 and avg_corner_brightness > 160)
        )
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Focus on top and bottom regions where navbars typically appear
        status_bar_height = int(height * 0.08)  # Top 8% for status bar (time, wifi, battery)
        navbar_height = int(height * 0.15)  # Top/bottom 15% for navbar
        
        status_bar_region = edges[:status_bar_height, :]
        top_region = edges[:navbar_height, :]
        bottom_region = edges[-navbar_height:, :]
        
        # === 1. CHECK STATUS BAR (time, WiFi, network, battery) ===
        # Look for small icons in the very top region
        status_bar_contours, _ = cv2.findContours(status_bar_region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        small_icons = 0  # WiFi, signal, battery, time etc
        icons_at_left = 0  # Left side icons (time)
        icons_at_right = 0  # Right side icons (battery, wifi, signal)
        icons_in_center = 0  # Center icons (should be 0 for real status bars)
        
        for contour in status_bar_contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Very small icons (6-35px) typical of status bar
            # STRICT: Must be within top 5% of image (not watch dial markers)
            if 6 < w < 35 and 6 < h < 35 and y < height * 0.05:
                small_icons += 1
                # Mobile status bars have icons on BOTH left and right, NOT center
                if x < width * 0.25:  # Stricter left boundary
                    icons_at_left += 1
                elif x > width * 0.75:  # Stricter right boundary
                    icons_at_right += 1
                elif width * 0.35 < x < width * 0.65:  # Center region
                    icons_in_center += 1
        
        # Check for text-like patterns in status bar (time display)
        status_bar_text_density = np.sum(status_bar_region > 0) / status_bar_region.size if status_bar_region.size > 0 else 0
        
        # STRICT: Need icons spread across status bar + some text + NO center icons
        # Watch faces often have center elements, mobile status bars do NOT
        has_status_bar = (
            small_icons >= 4 and 
            icons_at_left >= 2 and 
            icons_at_right >= 2 and 
            icons_in_center == 0 and  # Critical: no center icons
            status_bar_text_density > 0.02 and 
            status_bar_text_density < 0.15  # Not too dense (would be decorative)
        )
        
        # === 2. DETECT CIRCULAR BUTTONS (O, back arrows, menu dots) ===
        # UI buttons are typically small circles near edges
        circles_top = cv2.HoughCircles(
            gray[:navbar_height, :],
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=20,
            param1=50,
            param2=25,
            minRadius=8,
            maxRadius=40  # Reduced max - UI buttons are smaller
        )
        
        circles_bottom = cv2.HoughCircles(
            gray[-navbar_height:, :],
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=20,
            param1=50,
            param2=25,
            minRadius=8,
            maxRadius=40
        )
        
        # Filter circles: only count if near left/right edges (where UI buttons actually are)
        navbar_buttons_top = 0
        if circles_top is not None:
            for circle in circles_top[0]:
                x = circle[0]
                # UI buttons are at edges, not center (more lenient: 30% from edges)
                if x < width * 0.3 or x > width * 0.7:
                    navbar_buttons_top += 1
        
        navbar_buttons_bottom = 0
        if circles_bottom is not None:
            for circle in circles_bottom[0]:
                x = circle[0]
                if x < width * 0.3 or x > width * 0.7:
                    navbar_buttons_bottom += 1
        
        navbar_buttons_total = navbar_buttons_top + navbar_buttons_bottom
        
        # === 3. DETECT HORIZONTAL LINES (navbar separators) ===
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
        top_lines = cv2.morphologyEx(top_region, cv2.MORPH_OPEN, horizontal_kernel)
        bottom_lines = cv2.morphologyEx(bottom_region, cv2.MORPH_OPEN, horizontal_kernel)
        
        has_top_line = np.sum(top_lines > 0) > (width * 0.25)  # 25% of width
        has_bottom_line = np.sum(bottom_lines > 0) > (width * 0.25)
        
        # === 4. DETECT SMALL UI BUTTONS (X, ✓, share, bookmark, menu) ===
        contours_top, _ = cv2.findContours(top_region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_bottom, _ = cv2.findContours(bottom_region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        small_buttons_top = 0
        buttons_near_edge_top = 0
        
        for contour in contours_top:
            x, y, w, h = cv2.boundingRect(contour)
            # Small buttons (15-50px) - includes icons like X, share, menu
            if 15 < w < 50 and 15 < h < 50 and 0.4 < (w/h) < 2.5:
                small_buttons_top += 1
                # Check if near edges (more lenient: 30% from edges)
                if x < width * 0.3 or x > width * 0.7:
                    buttons_near_edge_top += 1
        
        small_buttons_bottom = 0
        buttons_near_edge_bottom = 0
        
        for contour in contours_bottom:
            x, y, w, h = cv2.boundingRect(contour)
            if 15 < w < 50 and 15 < h < 50 and 0.4 < (w/h) < 2.5:
                small_buttons_bottom += 1
                if x < width * 0.3 or x > width * 0.7:
                    buttons_near_edge_bottom += 1
        
        # === 5. PRODUCT PHOTO CHECK (EARLY EXIT) ===
        # Product photos with white backgrounds OR centered products are NOT screenshots
        if is_likely_product_photo:
            return {
                "passed": True,
                "reason": "Product photo detected - not a screenshot",
                "details": {
                    "is_product_photo": True,
                    "avg_corner_brightness": avg_corner_brightness,
                    "corner_uniformity": corner_std,
                    "center_vs_border_diff": center_vs_border_diff,
                    "background_variance": background_variance
                },
                "confidence": 0.0
            }
        
        # === 6. CALCULATE SCREENSHOT CONFIDENCE ===
        # ONLY flag as screenshot if we have CLEAR mobile phone UI patterns
        screenshot_confidence = 0.0
        navbar_detected = False
        detection_reasons = []
        
        # VERY STRICT: Must have actual status bar with icons on BOTH sides AND no center icons
        # This prevents product photos (especially watches) from being falsely detected
        has_actual_status_bar = (
            has_status_bar and 
            icons_at_left >= 2 and 
            icons_at_right >= 2 and 
            icons_in_center == 0
        )
        
        # Pattern 1: Perfect status bar + navbar buttons (STRONGEST PATTERN)
        if has_actual_status_bar and navbar_buttons_total >= 3:
            screenshot_confidence = 0.95
            navbar_detected = True
            detection_reasons.append("mobile_screenshot_with_navbar")
        
        # Pattern 2: Perfect status bar + top AND bottom UI elements (VERY STRONG)
        elif has_actual_status_bar and buttons_near_edge_top >= 2 and buttons_near_edge_bottom >= 2:
            screenshot_confidence = 0.95
            navbar_detected = True
            detection_reasons.append("mobile_screenshot_full_ui")
        
        # Pattern 3: Perfect status bar + clear UI buttons at edges (both top and bottom)
        elif has_actual_status_bar and buttons_near_edge_top >= 3 and buttons_near_edge_bottom >= 2:
            screenshot_confidence = 0.92
            navbar_detected = True
            detection_reasons.append("mobile_ui_with_buttons")
        
        # Pattern 4: Perfect status bar detection alone (with VERY strict criteria)
        elif has_actual_status_bar and small_icons >= 6 and navbar_buttons_total >= 2:
            screenshot_confidence = 0.92
            navbar_detected = True
            detection_reasons.append("confirmed_mobile_status_bar")
        
        # THRESHOLD: Only flag if we're very confident it's a mobile screenshot (>0.90)
        if navbar_detected and screenshot_confidence > 0.90:
            return {
                "passed": False,
                "reason": f"Mobile screenshot detected - {', '.join(detection_reasons)}",
                "details": {
                    "has_status_bar": has_status_bar,
                    "has_actual_status_bar": has_actual_status_bar,
                    "status_bar_icons": small_icons,
                    "icons_at_left": icons_at_left,
                    "icons_at_right": icons_at_right,
                    "icons_in_center": icons_in_center,
                    "circular_buttons_at_edges": navbar_buttons_total,
                    "buttons_near_edge_top": buttons_near_edge_top,
                    "buttons_near_edge_bottom": buttons_near_edge_bottom,
                    "top_line": has_top_line,
                    "bottom_line": has_bottom_line
                },
                "confidence": screenshot_confidence
            }
        
        return {
            "passed": True,
            "reason": "No mobile UI detected - not a screenshot",
            "details": {
                "status_bar_icons": small_icons,
                "icons_at_left": icons_at_left,
                "icons_at_right": icons_at_right,
                "icons_in_center": icons_in_center,
                "circular_buttons": navbar_buttons_total,
                "small_buttons_top": small_buttons_top,
                "buttons_near_edge": buttons_near_edge_top + buttons_near_edge_bottom,
                "is_product_photo": is_likely_product_photo
            },
            "confidence": 0.0
        }
    
    def detect_watermark(self, img_array: np.ndarray) -> Dict:
        """
        Detect 3rd party website watermarks (bikroy, daraz, etc.)
        Does NOT detect product names or brand logos
        """
        try:
            # Convert to grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            height, width = gray.shape
            
            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Check ONLY corners where website watermarks typically appear
            # Exclude center region (where product logos usually are)
            corner_regions = {
                'top_left': edges[0:height//5, 0:width//5],
                'top_right': edges[0:height//5, 4*width//5:width],
                'bottom_left': edges[4*height//5:height, 0:width//5],
                'bottom_right': edges[4*height//5:height, 4*width//5:width]
            }
            
            watermark_detected = False
            watermark_location = None
            max_density = 0
            
            for location, region in corner_regions.items():
                if region.size == 0:
                    continue
                
                # Calculate edge density
                edge_density = np.sum(region > 0) / region.size
                
                # Website watermarks have higher edge density (0.12-0.30)
                # This filters out simple product names
                if edge_density > 0.12 and edge_density < 0.30:
                    # Check for URL-like patterns (dots, multiple words)
                    horizontal_edges = np.sum(region, axis=0)
                    vertical_edges = np.sum(region, axis=1)
                    
                    # Website watermarks often have more complex patterns
                    if np.max(horizontal_edges) > region.shape[0] * 15 and np.std(horizontal_edges) > 5:
                        watermark_detected = True
                        if edge_density > max_density:
                            max_density = edge_density
                            watermark_location = location
            
            # Additional check: Look for semi-transparent overlays ONLY in corners
            if not watermark_detected:
                corner_regions_bright = [
                    gray[0:height//5, 0:width//5],
                    gray[0:height//5, 4*width//5:width],
                    gray[4*height//5:height, 0:width//5],
                    gray[4*height//5:height, 4*width//5:width]
                ]
                
                for region in corner_regions_bright:
                    if region.size == 0:
                        continue
                    std_dev = np.std(region)
                    mean_val = np.mean(region)
                    
                    # Very specific for semi-transparent website overlays
                    # Low variance + high brightness + small region = watermark
                    if std_dev < 25 and mean_val > 200 and region.size < (height * width) / 20:
                        watermark_detected = True
                        break
            
            return {
                "has_watermark": watermark_detected,
                "location": watermark_location,
                "confidence": max_density
            }
            
        except Exception as e:
            print(f"Warning: Watermark detection failed - {e}")
            return {
                "has_watermark": False,
                "location": None,
                "confidence": 0
            }
    
    def _check_watermark(self, img_array: np.ndarray) -> bool:
        """
        Check for watermarks using edge detection and text patterns
        Watermarks often appear as semi-transparent text or logos
        """
        try:
            # Convert to grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Check for diagonal patterns (common in watermarks)
            height, width = edges.shape
            
            # Sample regions (corners and center) where watermarks typically appear
            regions = [
                edges[0:height//4, 0:width//4],  # Top-left
                edges[0:height//4, 3*width//4:width],  # Top-right
                edges[3*height//4:height, 0:width//4],  # Bottom-left
                edges[3*height//4:height, 3*width//4:width],  # Bottom-right
                edges[height//3:2*height//3, width//3:2*width//3]  # Center
            ]
            
            watermark_detected = False
            for region in regions:
                if region.size == 0:
                    continue
                    
                # Calculate edge density
                edge_density = np.sum(region > 0) / region.size
                
                # High edge density in specific regions suggests watermark
                if edge_density > 0.15:
                    watermark_detected = True
                    break
            
            # Check for repeating patterns (tiled watermarks)
            if not watermark_detected:
                # Check for semi-transparent overlays by analyzing pixel intensity variance
                std_dev = np.std(gray)
                mean_intensity = np.mean(gray)
                
                # Watermarks often create subtle but consistent patterns
                # Check if there's unusual uniformity suggesting overlay
                if std_dev < 30 and mean_intensity > 200:
                    # Very uniform bright image might have watermark
                    watermark_detected = True
            
            # Return True if NO watermark detected (passed check)
            return not watermark_detected
            
        except Exception as e:
            print(f"Warning: Watermark check failed - {e}")
            return True  # If check fails, assume no watermark
