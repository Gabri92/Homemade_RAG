"""Local web chat over the pipeline (Gradio, ADR 0011). The only module that imports gradio.

No logic here: a question goes to `qa.answer()`, its citations to `qa.passages()`, and this
module only lays out what they return. Each citation can be checked at two depths: in the
chat, the cited chunk opens in place (what the model read); in the source panel, the whole
section is shown with that chunk marked.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from typing import Any

import gradio as gr

from homerag.config import DocumentEntry, ExperimentConfig, Settings, load_experiment
from homerag.ingest import load_book
from homerag.models import Answer, Book, Passage
from homerag.qa import Resources, answer, format_citation, format_usage, load_resources, passages

# Gradio's chat history: a list of message dicts ({"role", "content", "metadata"}), as the
# browser sends it back. Its shape is Gradio's, so it is not typed further here.
History = list[dict[str, Any]]

EMPTY_PANEL = (
    '<div class="source-empty">Ask a question: the sections the answer cites open here, '
    "with the passage the model read highlighted.</div>"
)

# Narrower than this, Gradio stacks the two columns: the source panel goes under the chat.
NARROW_PX = 720

# Up to this width the source column is narrow: its labels wrap, so the panel starts lower.
MEDIUM_PX = 1100

# Heights follow the window (dvh: the visible height, also on phones with a URL bar), so the
# question box and the panel stay in view on any screen. On a narrow screen the columns are
# stacked, so the chat and the panel each take most of the screen, and the header shrinks.
CSS = f"""
#chat {{ height: calc(100dvh - 340px) !important; min-height: 320px; }}
.source-panel {{ white-space: pre-wrap; line-height: 1.6; overflow-y: auto;
  max-height: calc(100dvh - 440px); min-height: 160px; }}
.source-panel mark {{ background: rgba(250, 199, 117, 0.45); color: inherit; padding: 1px 0; }}
.source-title {{ font-weight: 600; margin-bottom: 4px; white-space: normal; }}
.source-meta, .source-empty {{ opacity: 0.7; font-size: 0.9em; white-space: normal; }}
@media (max-width: {MEDIUM_PX}px) {{
  .source-panel {{ max-height: calc(100dvh - 520px); }}
}}
@media (max-width: {NARROW_PX}px) {{
  #doc-header h3 {{ font-size: 1.05em; margin-bottom: 2px; }}
  #doc-header p {{ font-size: 0.85em; margin: 2px 0; }}
  #chat {{ height: calc(100dvh - 365px) !important; min-height: 300px; }}
  .source-panel {{ max-height: 65dvh; }}
}}
"""

# A long section would open at its top, far from the passage: scroll the panel to the mark.
SCROLL_TO_MARK = """() => setTimeout(() => {
  const panel = document.querySelector(".source-panel");
  const mark = panel && panel.querySelector("mark");
  if (mark) panel.scrollTop = mark.offsetTop - panel.offsetTop - 24;
}, 50)"""

# On a narrow screen the panel is below the chat: picking a source scrolls the page to it.
SCROLL_TO_PANEL = f"""() => {{
  if (window.innerWidth <= {NARROW_PX}) {{
    document.querySelector("#sources")?.scrollIntoView({{ behavior: "smooth", block: "start" }});
  }}
}}"""


@dataclass(frozen=True, slots=True)
class ChatDocument:
    """A document ready to chat with: what the reader is told, and what answering needs."""

    entry: DocumentEntry
    cfg: ExperimentConfig
    resources: Resources
    book: Book


def open_documents(entries: Sequence[DocumentEntry], settings: Settings) -> list[ChatDocument]:
    """Load every document's index, models and book once, before the page opens."""
    documents = []
    for entry in entries:
        cfg = load_experiment(entry.config)
        documents.append(
            ChatDocument(entry, cfg, load_resources(cfg, settings), load_book(cfg.document))
        )
    return documents


def respond(
    question: str, history: History, document: ChatDocument
) -> tuple[History, list[str], dict[str, str]]:
    """Answer one question: the chat with the new turn, the source labels, their panels."""
    if not question.strip():
        return history, [], {}
    result = answer(question.strip(), document.resources, document.cfg)
    panels = {
        format_citation(p.citation): source_panel(p, document.entry)
        for p in passages(result, document.book)
    }
    return [*history, *chat_messages(result)], list(panels), panels


def chat_messages(result: Answer) -> History:
    """The question, the answer with its cost, then each cited chunk as a collapsed message."""
    text = result.text
    if result.usage:
        text += f"\n\n<sub>{format_usage(result.usage)}</sub>"
    messages: History = [
        {"role": "user", "content": result.question},
        {"role": "assistant", "content": text},
    ]
    cited = sorted({c.source for c in result.citations})
    for n in cited:
        chunk = result.retrieved[n - 1].chunk
        sections = "; ".join(" > ".join(s.path) for s in chunk.sections)
        page = f", p. {chunk.page}" if chunk.page else ""
        messages.append(
            {
                "role": "assistant",
                "content": chunk.text,
                "metadata": {"title": f"[{n}] {sections}{page}", "status": "done"},
            }
        )
    return messages


def source_panel(passage: Passage, entry: DocumentEntry) -> str:
    """One cited section as HTML: its path and pages, its text with the read part marked."""
    c = passage.citation
    page = f"Page {escape(c.page)} · " if c.page else ""
    return (
        f'<div class="source-title">{escape(" > ".join(c.section_path))}</div>'
        f'<div class="source-meta">{page}highlighted: the passage the model read as '
        f"source [{c.source}]</div>"
        f'<div class="source-panel">{escape(passage.before)}<mark>{escape(passage.read)}</mark>'
        f"{escape(passage.after)}</div>"
        f'<div class="source-meta">From <a href="{escape(entry.url)}" target="_blank">'
        f"{escape(entry.title)}</a>, {escape(entry.author)}, "
        f'<a href="{escape(entry.license_url)}" target="_blank">{escape(entry.license)}</a>.'
        "</div>"
    )


def header(entry: DocumentEntry) -> str:
    """Markdown above the chat: the document, its author and license, a link to read it."""
    return (
        f"### {entry.title}\n"
        f"{entry.author} · [{entry.license}]({entry.license_url}) · "
        f"[Read the book online]({entry.url})\n\n"
        "Answers come only from this document, in English, with numbered sources: open a "
        "source to check the answer against the text. Not medical advice."
    )


def build_app(documents: Sequence[ChatDocument]) -> gr.Blocks:
    """The page: document menu and chat on the left, the cited section on the right."""
    by_title = {d.entry.title: d for d in documents}
    first = documents[0]
    app = gr.Blocks(title="homerag", analytics_enabled=False)
    with app:
        top = gr.Markdown(header(first.entry), elem_id="doc-header")
        with gr.Row():
            # min_width decides when the columns stack: both fit side by side from NARROW_PX.
            with gr.Column(scale=3, min_width=340):
                menu = gr.Dropdown(list(by_title), value=first.entry.title, label="Document")
                chat = gr.Chatbot(label="Chat", buttons=["copy"], elem_id="chat")
                box = gr.Textbox(
                    placeholder="Ask a question about the document, in English",
                    show_label=False,
                    submit_btn=True,
                )
            with gr.Column(scale=2, min_width=300):
                sources = gr.Radio([], label="Sources of the last answer", elem_id="sources")
                panel = gr.HTML(EMPTY_PANEL)
        panels = gr.State({})

        def ask(question: str, history: History, title: str) -> tuple[Any, ...]:
            history, labels, found = respond(question, history, by_title[title])
            first_label = labels[0] if labels else None
            shown = found[first_label] if first_label else EMPTY_PANEL
            return history, gr.Radio(labels, value=first_label), shown, found, ""

        def show(label: str | None, found: dict[str, str]) -> str:
            return found.get(label or "", EMPTY_PANEL)

        def switch(title: str) -> tuple[Any, ...]:
            return header(by_title[title].entry), [], gr.Radio([], value=None), EMPTY_PANEL, {}

        box.submit(ask, [box, chat, menu], [chat, sources, panel, panels, box])
        sources.input(show, [sources, panels], panel)
        sources.input(None, js=SCROLL_TO_PANEL)
        menu.change(switch, menu, [top, chat, sources, panel, panels])
        panel.change(None, js=SCROLL_TO_MARK)
    return app


def launch(documents: Sequence[ChatDocument], port: int) -> None:
    """Serve the chat on this machine only (no public link), until Ctrl+C."""
    build_app(documents).launch(
        server_name="127.0.0.1", server_port=port, share=False, inbrowser=False, css=CSS
    )
