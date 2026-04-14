import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { ReaderChapter } from "../lib/generated-data";
import { compactSummary, formatDateTime, formatPageRange, stripGuideDots } from "../lib/formatters";
import { parsePartIntroText, stripPartIntroSection } from "../lib/part-intro";
import { enhanceReaderHtml } from "../lib/reader-html";

type ReaderArticleProps = {
  chapter: ReaderChapter;
  partChapters: ReaderChapter[];
  activeSectionId: string;
  builtAt: string;
};

const DEFAULT_PART_GUIDE_DESCRIPTION = "이 편은 다음 장으로 구성됩니다.";

export function ReaderArticle({ chapter, partChapters, activeSectionId, builtAt }: ReaderArticleProps): JSX.Element {
  const articleRef = useRef<HTMLElement | null>(null);
  const heroRef = useRef<HTMLElement | null>(null);
  const [isOutlineOpen, setIsOutlineOpen] = useState(() => window.matchMedia("(min-width: 62rem)").matches);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(min-width: 62rem)");
    const syncOutlineState = (): void => {
      setIsOutlineOpen(mediaQuery.matches);
    };

    syncOutlineState();
    mediaQuery.addEventListener("change", syncOutlineState);

    return () => {
      mediaQuery.removeEventListener("change", syncOutlineState);
    };
  }, [chapter.slug]);

  const headingDepthById = useMemo(() => {
    return new Map(chapter.headings.map((heading) => [heading.id, heading.depth]));
  }, [chapter.headings]);
  const partIntroEntry = useMemo(
    () => chapter.sectionCatalog.find((entry) => entry.entryType === "part-intro") ?? null,
    [chapter.sectionCatalog]
  );
  const partIntroContent = useMemo(() => {
    const parsed = parsePartIntroText(partIntroEntry?.text ?? "");
    if (parsed.description || parsed.items.length > 0) {
      return parsed;
    }

    return {
      description: DEFAULT_PART_GUIDE_DESCRIPTION,
      items: [],
    };
  }, [partIntroEntry?.text]);
  const currentChapterIndex = useMemo(
    () => partChapters.findIndex((partChapter) => partChapter.slug === chapter.slug),
    [chapter.slug, partChapters]
  );
  const firstPartChapter = partChapters[0] ?? null;
  const lastPartChapter = partChapters[partChapters.length - 1] ?? null;
  const previousChapter = currentChapterIndex > 0 ? partChapters[currentChapterIndex - 1] ?? null : null;
  const nextChapter =
    currentChapterIndex >= 0 && currentChapterIndex + 1 < partChapters.length
      ? partChapters[currentChapterIndex + 1] ?? null
      : null;
  const enhancedHtml = useMemo(
    () => enhanceReaderHtml(stripPartIntroSection(chapter.html)),
    [chapter.html]
  );

  useEffect(() => {
    const articleNode = articleRef.current;
    const heroNode = heroRef.current;

    if (!articleNode) {
      return;
    }

    for (const heading of articleNode.querySelectorAll("h2, h3")) {
      heading.textContent = stripGuideDots(heading.textContent);
    }

    for (const section of articleNode.querySelectorAll("section")) {
      section.classList.remove("is-target");
    }

    const targetId = activeSectionId || "overview";
    const targetElement =
      targetId === "overview"
        ? heroNode
        : articleNode.querySelector<HTMLElement>(`section[id="${CSS.escape(targetId)}"]`);

    if (!targetElement) {
      return;
    }

    if (targetId !== "overview") {
      targetElement.classList.add("is-target");
    }

    requestAnimationFrame(() => {
      targetElement.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [activeSectionId, enhancedHtml]);

  return (
    <article ref={articleRef} className="reader-column">
      <header ref={heroRef} className="surface chapter-hero">
        <div className="chapter-hero-copy">
          <span className="eyebrow">{chapter.partTitle}</span>
          <h1>{chapter.displayTitle}</h1>
          <p>{chapter.summary}</p>
        </div>
        <div className="meta-grid">
          <div className="meta-card">
            <span className="meta-label">페이지</span>
            <strong>
              {formatPageRange(chapter.pageStart, chapter.pageEnd, chapter.pageLabelStart, chapter.pageLabelEnd)}
            </strong>
          </div>
          <div className="meta-card">
            <span className="meta-label">시작 라벨</span>
            <strong>{chapter.pageLabelStart || chapter.pageLabel || "미상"}</strong>
          </div>
          <div className="meta-card">
            <span className="meta-label">이미지</span>
            <strong>{chapter.hasImage ? `${chapter.imageCount}개 포함` : "없음"}</strong>
          </div>
          <div className="meta-card">
            <span className="meta-label">build</span>
            <strong>{formatDateTime(builtAt)}</strong>
          </div>
        </div>
      </header>

      <section className="surface chapter-outline" aria-label="현재 장 개요와 섹션 이동">
        <div className="outline-header">
          <div>
            <span className="eyebrow">Chapter outline</span>
            <h2>장 개요와 섹션 이동</h2>
          </div>
          <button
            type="button"
            className="outline-toggle"
            aria-expanded={isOutlineOpen}
            onClick={() => setIsOutlineOpen((current) => !current)}
          >
            {isOutlineOpen ? "접기" : "펼치기"}
          </button>
        </div>

        {isOutlineOpen ? (
          <nav className="outline-list" aria-label="현재 장 섹션 이동">
            {chapter.sectionCatalog.map((entry) => {
              const isActive = entry.sectionId === (activeSectionId || "overview");
              const depth = entry.sectionId === "overview" ? 2 : headingDepthById.get(entry.sectionId) ?? 3;

              return (
                <Link
                  key={`${chapter.slug}-${entry.sectionId}`}
                  to={entry.routePath}
                  className={`outline-link${isActive ? " is-active" : ""}`}
                  data-depth={depth}
                >
                  <span className="outline-link-title">{stripGuideDots(entry.sectionTitle)}</span>
                  <span className="outline-link-meta">
                    {formatPageRange(entry.pageStart, entry.pageEnd, entry.pageLabelStart, entry.pageLabelEnd)}
                  </span>
                </Link>
              );
            })}
          </nav>
        ) : null}
      </section>

      {partChapters.length > 0 ? (
        <section
          id="part-intro"
          className={`surface chapter-part-intro${activeSectionId === "part-intro" ? " is-target" : ""}`}
        >
          <div className="section-heading compact">
            <span className="eyebrow">Part Guide</span>
            <h2>{chapter.partTitle}</h2>
          </div>
          <p>{partIntroContent.description || DEFAULT_PART_GUIDE_DESCRIPTION}</p>
          {partChapters.length > 0 ? (
            <div className="part-intro-quick-nav" aria-label="같은 편 안의 장 이동">
              {previousChapter ? (
                <Link to={previousChapter.sectionCatalog[0]?.routePath ?? "#"} className="part-intro-jump">
                  <span className="eyebrow">이전 장</span>
                  <strong>{previousChapter.displayTitle}</strong>
                </Link>
              ) : (
                <div className="part-intro-jump is-disabled">
                  <span className="eyebrow">이전 장</span>
                  <strong>없음</strong>
                </div>
              )}

              <div className="part-intro-position">
                <span className="eyebrow">현재 위치</span>
                <strong>
                  {currentChapterIndex >= 0 ? `${currentChapterIndex + 1} / ${partChapters.length}` : `1 / ${partChapters.length}`}
                </strong>
              </div>

              {nextChapter ? (
                <Link to={nextChapter.sectionCatalog[0]?.routePath ?? "#"} className="part-intro-jump">
                  <span className="eyebrow">다음 장</span>
                  <strong>{nextChapter.displayTitle}</strong>
                </Link>
              ) : (
                <div className="part-intro-jump is-disabled">
                  <span className="eyebrow">다음 장</span>
                  <strong>없음</strong>
                </div>
              )}
            </div>
          ) : null}
          {partChapters.length > 0 ? (
            <div className="part-intro-grid">
              {partChapters.map((partChapter) => {
                const defaultEntry =
                  partChapter.sectionCatalog.find((entry) => entry.sectionId === "overview") ?? partChapter.sectionCatalog[0];

                return (
                  <Link
                    key={partChapter.slug}
                    to={defaultEntry?.routePath ?? "#"}
                    className={`part-intro-link${partChapter.slug === chapter.slug ? " is-active" : ""}`}
                    aria-current={partChapter.slug === chapter.slug ? "page" : undefined}
                  >
                    <span className="part-intro-link-header">
                      <strong>{partChapter.displayTitle}</strong>
                      {partChapter.slug === chapter.slug ? <span className="part-intro-active-badge">현재 장</span> : null}
                    </span>
                    <span className="part-intro-link-summary">{compactSummary(partChapter.summary, 112)}</span>
                    <span className="part-intro-item-meta">
                      {formatPageRange(
                        partChapter.pageStart,
                        partChapter.pageEnd,
                        partChapter.pageLabelStart,
                        partChapter.pageLabelEnd
                      )}
                    </span>
                  </Link>
                );
              })}
            </div>
          ) : partIntroContent.items.length > 0 ? (
            <div className="part-intro-grid">
              {partIntroContent.items.map((item) => (
                <p key={item} className="part-intro-item">
                  {item}
                </p>
              ))}
            </div>
          ) : null}
          {firstPartChapter && lastPartChapter ? (
            <div className="result-meta">
              <span>
                {formatPageRange(
                  firstPartChapter.pageStart,
                  lastPartChapter.pageEnd,
                  firstPartChapter.pageLabelStart,
                  lastPartChapter.pageLabelEnd
                )}
              </span>
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="surface reader-article" dangerouslySetInnerHTML={{ __html: enhancedHtml }} />

      <nav className="surface chapter-pager" aria-label="같은 편 안의 장 이동">
        {previousChapter ? (
          <Link to={previousChapter.sectionCatalog[0]?.routePath ?? "#"} className="part-intro-jump">
            <span className="eyebrow">이전 장</span>
            <strong>{previousChapter.displayTitle}</strong>
          </Link>
        ) : (
          <div className="part-intro-jump is-disabled">
            <span className="eyebrow">이전 장</span>
            <strong>없음</strong>
          </div>
        )}

        <div className="chapter-pager-center">
          <span className="eyebrow">같은 편</span>
          <strong>{currentChapterIndex >= 0 ? `${currentChapterIndex + 1} / ${partChapters.length}` : "미상"}</strong>
        </div>

        {nextChapter ? (
          <Link to={nextChapter.sectionCatalog[0]?.routePath ?? "#"} className="part-intro-jump">
            <span className="eyebrow">다음 장</span>
            <strong>{nextChapter.displayTitle}</strong>
          </Link>
        ) : (
          <div className="part-intro-jump is-disabled">
            <span className="eyebrow">다음 장</span>
            <strong>없음</strong>
          </div>
        )}
      </nav>
    </article>
  );
}
