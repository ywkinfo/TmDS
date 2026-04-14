import { Link } from "react-router-dom";

import type { ReaderChapter, ReaderPart } from "../lib/generated-data";
import { formatPageRange } from "../lib/formatters";

type TocPanelProps = {
  parts: ReaderPart[];
  currentChapter: ReaderChapter | null;
  onNavigate?: () => void;
};

function ImageBadge({ hasImage, imageCount }: { hasImage: boolean; imageCount: number }): JSX.Element | null {
  if (!hasImage) {
    return null;
  }

  return (
    <span className="badge badge-image" aria-label={imageCount > 0 ? `이미지 ${imageCount}개 포함` : "이미지 포함"}>
      이미지
      {imageCount > 0 ? <span className="badge-count">{imageCount}</span> : null}
    </span>
  );
}

export function TocPanel({ parts, currentChapter, onNavigate }: TocPanelProps): JSX.Element {
  return (
    <div className="toc-stack">
      {parts.map((part) => (
        <section key={part.id} className="toc-group">
          <div className="toc-group-header">
            <span className="eyebrow">{part.label}</span>
            <h2>{part.title}</h2>
          </div>
          <div className="toc-list">
            {part.chapters.map((chapter) => {
              const isActive = currentChapter?.slug === chapter.slug;

              return (
                <Link
                  key={chapter.slug}
                  to={chapter.sectionCatalog[0]?.routePath}
                  className={`toc-link${isActive ? " is-active" : ""}`}
                  onClick={onNavigate}
                >
                  <span className="toc-title-row">
                    <strong>{chapter.displayTitle}</strong>
                    <ImageBadge hasImage={chapter.hasImage} imageCount={chapter.imageCount} />
                  </span>
                  <span className="toc-meta-row">
                    <span>
                      {formatPageRange(
                        chapter.pageStart,
                        chapter.pageEnd,
                        chapter.pageLabelStart,
                        chapter.pageLabelEnd
                      )}
                    </span>
                    <span>{chapter.tocItemCount}개 항목</span>
                  </span>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
