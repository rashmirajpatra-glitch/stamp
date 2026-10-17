from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from stamp_agent.config import load_rules, load_settings
from stamp_agent.pipeline import StampIntelligencePipeline, build_sarvam_client


def create_synthetic_demo_image(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", (1000, 700), "white")
    draw = ImageDraw.Draw(image)

    # Stamp/seal (red circular imprint)
    draw.ellipse((600, 460, 780, 640), outline=(220, 20, 20), width=10)
    draw.text((635, 540), "AUTHORITY", fill=(220, 20, 20))

    # Signature-like strokes (dark ink)
    stroke_points = [
        (200, 610),
        (260, 590),
        (315, 625),
        (385, 585),
        (455, 620),
        (530, 600),
    ]
    draw.line(stroke_points, fill=(10, 10, 10), width=7)
    draw.line([(540, 600), (640, 630)], fill=(10, 10, 10), width=5)

    image.save(target)
    return target


def run_demo(output_dir: str | Path | None = None) -> str:
    settings = load_settings()
    settings.sarvam_use_mock = True
    rules = load_rules(None)
    pipeline = StampIntelligencePipeline(settings=settings, rules=rules, sarvam_client=build_sarvam_client(settings))

    out_dir = Path(output_dir).expanduser().resolve() if output_dir else settings.output_dir
    sample_image = create_synthetic_demo_image(out_dir / "demo_input.png")

    result = pipeline.analyze(sample_image, output_dir=out_dir)
    return (
        "Demo completed\n"
        f"Input: {sample_image}\n"
        f"Verdict: {result.report.verdict.value}\n"
        f"Confidence: {result.report.overall_confidence:.4f}\n"
        f"Report: {result.report_path}\n"
        f"Email sent: {result.email_sent}"
    )


if __name__ == "__main__":
    print(run_demo())
