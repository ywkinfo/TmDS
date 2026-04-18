import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

type ReviewParagraph = {
  index: number;
  text: string;
  sourceBlocks: number[];
  sourceLines: number[];
  kind: string;
  boundaryReason: string;
};

type ReviewLine = {
  index: number;
  blockIndex: number;
  legacyBlockIndex: number;
  lineIndex: number;
  text: string;
  kind: string;
  centered: boolean;
  fontSize: number;
  fontFlags: number;
  spanCount: number;
  sourceSpanTexts: string[];
};

type ReviewPage = {
  pageNumber: number;
  pageLabel: string | null;
  chapterSlug: string | null;
  sectionId: string | null;
  sourceBlocks: Array<{ index: number; text: string; kind: string }>;
  sourceLines: ReviewLine[];
  paragraphs: ReviewParagraph[];
  paragraphCount: number;
  hasOverride: boolean;
  mergeFirstGroupWithPreviousPage: boolean;
  pageLayoutKind: string;
  confidence: string;
  dominantBodyFont: number | null;
  bodyLeftAnchor: number;
  baseLineGap: number;
};

type AuditPage = {
  pageNumber: number;
  riskTier: string;
  flags: string[];
};

type AuditReport = {
  pages: AuditPage[];
};

type LoadState =
  | { status: "loading" }
  | { status: "missing" }
  | { status: "ready"; pages: ReviewPage[]; auditPagesByNumber: Record<number, AuditPage> };

function generatedUrl(fileName: string): string {
  return new URL(`../generated/${fileName}`, document.baseURI).toString();
}

export function QAPage(): JSX.Element {
  const navigate = useNavigate();
  const { pageNumber: pageNumberParam } = useParams();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [jumpValue, setJumpValue] = useState(pageNumberParam ?? "5");

  useEffect(() => {
    let cancelled = false;

    const reviewPromise = fetch(generatedUrl("page-review.json")).then((response) => {
      if (!response.ok) {
        throw new Error(String(response.status));
      }
      return response.json() as Promise<ReviewPage[]>;
    });

    const auditPromise = fetch(generatedUrl("page-audit-report.json"))
      .then((response) => {
        if (!response.ok) {
          return null;
        }
        return response.json() as Promise<AuditReport>;
      })
      .catch(() => null);

    Promise.all([reviewPromise, auditPromise])
      .then(([pages, auditReport]) => {
        if (!cancelled) {
          const auditPagesByNumber = Object.fromEntries(
            (auditReport?.pages ?? []).map((auditPage) => [auditPage.pageNumber, auditPage])
          );
          setState({ status: "ready", pages, auditPagesByNumber });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: "missing" });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const currentPageNumber = Number(pageNumberParam ?? "5");
  const page = useMemo(() => {
    if (state.status !== "ready") {
      return null;
    }
    return state.pages.find((candidate) => candidate.pageNumber === currentPageNumber) ?? null;
  }, [currentPageNumber, state]);

  const flaggedPages = useMemo(() => {
    if (state.status !== "ready") {
      return [];
    }
    return state.pages
      .filter((candidate) => {
        const auditPage = state.auditPagesByNumber[candidate.pageNumber];
        return (auditPage?.flags.length ?? 0) > 0 || candidate.hasOverride || candidate.confidence === "low";
      })
      .map((candidate) => candidate.pageNumber);
  }, [state]);

  function handleJump(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const target = Number(jumpValue);
    if (!Number.isFinite(target) || target < 1) {
      return;
    }
    navigate(`/qa/page/${target}`);
  }

  if (state.status === "loading") {
    return (
      <div className="page-stack">
        <section className="surface status-card">
          <span className="eyebrow">QA</span>
          <h1>페이지별 검수 데이터를 불러오고 있습니다.</h1>
        </section>
      </div>
    );
  }

  if (state.status === "missing") {
    return (
      <div className="page-stack">
        <section className="surface status-card error-state">
          <span className="eyebrow">QA</span>
          <h1>QA 자산이 아직 없습니다.</h1>
          <p>
            먼저 <code>npm run qa:prepare</code>를 실행한 뒤 이 페이지를 다시 열어 주세요.
          </p>
        </section>
      </div>
    );
  }

  if (!page) {
    return (
      <div className="page-stack">
        <section className="surface status-card error-state">
          <span className="eyebrow">QA</span>
          <h1>해당 페이지 검수 데이터를 찾지 못했습니다.</h1>
        </section>
      </div>
    );
  }

  const previousPage = page.pageNumber > 1 ? page.pageNumber - 1 : null;
  const nextPage = page.pageNumber + 1 <= state.pages.length ? page.pageNumber + 1 : null;
  const imageUrl = generatedUrl(`review-pages/${String(page.pageNumber).padStart(4, "0")}.jpg`);
  const currentFlaggedIndex = flaggedPages.indexOf(page.pageNumber);
  const previousFlaggedPage = currentFlaggedIndex > 0 ? flaggedPages[currentFlaggedIndex - 1] : null;
  const nextFlaggedPage =
    currentFlaggedIndex >= 0 && currentFlaggedIndex + 1 < flaggedPages.length ? flaggedPages[currentFlaggedIndex + 1] : null;
  const auditPage = state.status === "ready" ? state.auditPagesByNumber[page.pageNumber] ?? null : null;
  const pageFlags = auditPage?.flags ?? [];

  return (
    <div className="page-stack">
      <section className="surface chapter-hero">
        <div className="chapter-hero-copy">
          <span className="eyebrow">QA Review</span>
          <h1>
            page {page.pageNumber}
            {page.pageLabel ? ` · p.${page.pageLabel}` : ""}
          </h1>
          <p>
            chapter: {page.chapterSlug ?? "미상"} / section: {page.sectionId ?? "미상"} / layout: {page.pageLayoutKind} / confidence:{" "}
            {page.confidence}
          </p>
          <p>
            override: {page.hasOverride ? "yes" : "no"} / mergeFirstGroupWithPreviousPage:{" "}
            {page.mergeFirstGroupWithPreviousPage ? "yes" : "no"} / dominantBodyFont: {page.dominantBodyFont ?? "n/a"} / baseLineGap:{" "}
            {page.baseLineGap}
          </p>
          <p>
            risk tier: {auditPage?.riskTier ?? "n/a"} / flags: {pageFlags.length > 0 ? pageFlags.join(", ") : "none"}
          </p>
        </div>
        <form className="search-form" onSubmit={handleJump}>
          <input value={jumpValue} onChange={(event) => setJumpValue(event.target.value)} inputMode="numeric" />
          <button type="submit" className="search-reset">
            이동
          </button>
        </form>
      </section>

      <nav className="surface chapter-pager" aria-label="QA 페이지 이동">
        {previousPage ? (
          <Link to={`/qa/page/${previousPage}`} className="part-intro-jump">
            <span className="eyebrow">이전 페이지</span>
            <strong>{previousPage}</strong>
          </Link>
        ) : (
          <div className="part-intro-jump is-disabled">
            <span className="eyebrow">이전 페이지</span>
            <strong>없음</strong>
          </div>
        )}

        <div className="chapter-pager-center">
          <span className="eyebrow">문단 수</span>
          <strong>{page.paragraphCount}</strong>
        </div>

        {nextPage ? (
          <Link to={`/qa/page/${nextPage}`} className="part-intro-jump">
            <span className="eyebrow">다음 페이지</span>
            <strong>{nextPage}</strong>
          </Link>
        ) : (
          <div className="part-intro-jump is-disabled">
            <span className="eyebrow">다음 페이지</span>
            <strong>없음</strong>
          </div>
        )}
      </nav>

      <section className="surface chapter-pager" aria-label="QA 플래그 이동">
        {previousFlaggedPage ? (
          <Link to={`/qa/page/${previousFlaggedPage}`} className="part-intro-jump">
            <span className="eyebrow">이전 플래그</span>
            <strong>{previousFlaggedPage}</strong>
          </Link>
        ) : (
          <div className="part-intro-jump is-disabled">
            <span className="eyebrow">이전 플래그</span>
            <strong>없음</strong>
          </div>
        )}

        <div className="chapter-pager-center">
          <span className="eyebrow">Flagged Pages</span>
          <strong>{flaggedPages.length}</strong>
        </div>

        {nextFlaggedPage ? (
          <Link to={`/qa/page/${nextFlaggedPage}`} className="part-intro-jump">
            <span className="eyebrow">다음 플래그</span>
            <strong>{nextFlaggedPage}</strong>
          </Link>
        ) : (
          <div className="part-intro-jump is-disabled">
            <span className="eyebrow">다음 플래그</span>
            <strong>없음</strong>
          </div>
        )}
      </section>

      <section className="qa-review-grid">
        <div className="surface qa-panel">
          <div className="section-heading compact">
            <span className="eyebrow">PDF</span>
            <h2>원본 페이지</h2>
          </div>
          <img className="qa-page-image" src={imageUrl} alt={`page ${page.pageNumber}`} />
        </div>

        <div className="surface qa-panel">
          <div className="section-heading compact">
            <span className="eyebrow">Paragraphs</span>
            <h2>현재 문단 분할</h2>
          </div>
          <div className="qa-paragraph-stack">
            {page.paragraphs.map((paragraph) => (
              <article key={paragraph.index} className="qa-paragraph-card">
                <div className="result-meta">
                  <span>문단 {paragraph.index + 1}</span>
                  <span>{paragraph.kind}</span>
                  <span>blocks: {paragraph.sourceBlocks.join(", ")}</span>
                  <span>lines: {paragraph.sourceLines.join(", ")}</span>
                  <span>reason: {paragraph.boundaryReason}</span>
                </div>
                <p>{paragraph.text}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="surface qa-panel">
          <div className="section-heading compact">
            <span className="eyebrow">Lines</span>
            <h2>원본 line 추출</h2>
          </div>
          <div className="qa-paragraph-stack">
            {page.sourceLines.map((line) => (
              <article key={line.index} className="qa-paragraph-card">
                <div className="result-meta">
                  <span>line {line.index}</span>
                  <span>{line.kind}</span>
                  <span>block {line.legacyBlockIndex}</span>
                  <span>font {line.fontSize}</span>
                  <span>{line.centered ? "centered" : "aligned"}</span>
                </div>
                <p>{line.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
