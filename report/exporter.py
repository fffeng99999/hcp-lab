import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def render_tex(template: str, title: str, summary: str, figures: List[str]) -> str:
    figure_block = "\n".join(
        [f"\\includegraphics[width=0.9\\linewidth]{{{f}}}" for f in figures]
    )
    content = template.replace("{title}", title)
    content = content.replace("{summary}", summary)
    content = content.replace("{figures}", figure_block)
    return content


def export_markdown(
    output_dir: Path,
    title: str,
    summary: str,
    figures: Optional[List[str]] = None,
) -> Dict[str, Optional[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "report.md"
    md_content = f"# {title}\n\n## 摘要\n{summary}\n"
    if figures:
        md_content += "\n## 图表\n"
        for fig in figures:
            md_content += f"\n![]({fig})\n"
    md_path.write_text(md_content, encoding="utf-8")
    return {"md": str(md_path)}


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
    engine = "xelatex" if shutil.which("xelatex") else "pdflatex"
    try:
        subprocess.run(
            [engine, "-interaction=nonstopmode", tex_path.name],
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
