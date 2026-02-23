import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def render_tex(template: str, title: str, summary: str, figures: List[str]) -> str:
    figure_block = "\n".join([f"\\includegraphics[width=0.9\\linewidth]{{{f}}}" for f in figures])
    return template.format(title=title, summary=summary, figures=figure_block)


def export_pdf(
    template_path: Path,
    output_dir: Path,
    title: str,
    summary: str,
    figures: List[str],
) -> Dict[str, Optional[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    template = template_path.read_text(encoding="utf-8")
    tex_content = render_tex(template, title, summary, figures)
    tex_path = output_dir / "report.tex"
    tex_path.write_text(tex_content, encoding="utf-8")
    pdf_path = output_dir / "report.pdf"
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_path.name],
            cwd=str(output_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        if pdf_path.exists():
            return {"pdf": str(pdf_path), "tex": str(tex_path)}
    except Exception:
        return {"pdf": None, "tex": str(tex_path)}
    return {"pdf": None, "tex": str(tex_path)}
