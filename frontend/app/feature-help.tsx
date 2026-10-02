/** Descriptions match the pinned v7.1 feature contract. */
const descriptions: Record<string, string> = {
  title_similarity: 'Embedding similarity between the target query and the original page title.',
  h1_similarity: 'Best embedding similarity between the query and an H1 heading, when several exist.',
  outline_similarity: 'Embedding similarity between the query and the page’s heading outline.',
  page_similarity: 'Embedding similarity between the query and the whole page. Long pages use pooled chunk embeddings.',
  path_similarity: 'Embedding similarity between the query and the normalized URL path.',
  section_max: 'The highest query similarity among section chunks: how well the single best passage matches.',
  section_top3_mean: 'Average query similarity of the three best section chunks, or all chunks if fewer than three.',
  section_median: 'The middle query similarity across section chunks: how well a typical chunk matches.',
  section_q25: 'The 25th percentile of section-chunk query similarity. Roughly one quarter of chunks score below this level.',
  section_q75: 'The 75th percentile of section-chunk query similarity. Roughly three quarters of chunks score below this level.',
  prompt_question: 'Whether the query starts with a recognized question word or contains a question mark (1=yes, 0=no).',
  prompt_comparison: 'Whether the query contains a comparison cue such as best, compare, versus or cheapest (1=yes, 0=no).',
  prompt_how_to: 'Whether the query contains “how to” (1=yes, 0=no).',
  path_depth: 'Number of nonempty segments in the URL path. The hostname is not counted.',
  path_homepage: 'Whether the URL path is empty or just / (1=yes, 0=no).',
  path_editorial: 'Whether the URL path matches the scorer’s editorial-page keyword rules (1=yes, 0=no).',
  path_commerce: 'Whether the URL path matches the scorer’s commerce-page keyword rules (1=yes, 0=no).',
  path_support_docs: 'Whether the URL path matches the scorer’s support/documentation keyword rules (1=yes, 0=no).',
  headings_per_1000_words: 'Heading count divided by total scored word occurrences, multiplied by 1,000. Measures heading density.',
  list_items_per_1000_words: 'List-item count divided by total scored word occurrences, multiplied by 1,000.',
  links_per_1000_words: 'Retained link count divided by total scored word occurrences, multiplied by 1,000.',
  has_table: 'Whether the parsed scoring view contains a table (1=yes, 0=no).',
  has_list: 'Whether the parsed scoring view contains a list (1=yes, 0=no).',
  has_jsonld: 'Whether the original source metadata includes JSON-LD entries (1=yes, 0=no).',
  has_article_schema: 'Whether source JSON-LD declares a recognized article-like schema type (1=yes, 0=no).',
  empty_title: 'Whether the original page title is empty (1=yes, 0=no).',
  retained_text_fraction: 'Scored word count divided by original source word count, capped at 1. The original denominator stays fixed for a rewrite; expansion or shortening can change this diagnostic.',
  needs_review: 'Whether extraction selected the document with a needs-review status (1=yes, 0=no).',
  possible_error_response: 'Whether extraction flagged a possible error page (1=yes, 0=no).',
  sparse_body: 'Whether the scoring view contains 30 or fewer words (1=yes, 0=no).',
  format_html: 'Whether the original source format is HTML (1=yes, 0=no).',
  paragraph_log_median_words: 'Natural log of 1 plus the median paragraph word count. Describes a typical paragraph’s length; 0 when there are none.',
  paragraph_log_p90_words: 'Natural log of 1 plus the 90th-percentile paragraph word count. Describes longer paragraphs; 0 when there are none.',
  short_paragraph_fraction: 'Number of paragraphs with 10–60 words divided by the number of paragraphs; 0 when there are none.',
  unique_word_fraction: 'Distinct normalized words divided by total word occurrences. “Cats like cats” gives 2/3. Vocabulary variety also depends on page length.',
  numeric_word_fraction: 'Share of word tokens containing at least one digit.',
  question_heading_fraction: 'Share of headings containing a ? character.',
  duplicate_heading_fraction: '1 minus distinct heading texts divided by heading count, ignoring capitalization; 0 with no headings.',
};
const logCounts: Record<string, string> = {
  log_prompt_words: 'query word count', log_word_count: 'total scored word count',
  log_title_words: 'original title word count', log_heading_count: 'heading count',
  log_h1_count: 'H1 heading count', log_list_items: 'list-item count',
  log_table_count: 'table count', log_paragraph_count: 'paragraph count',
  log_code_count: 'code-block count', log_ordered_steps: 'number of list items with an ordered-list parent',
  log_source_script_count: 'original source script count', log_link_count: 'retained link count',
};
for (const [name, count] of Object.entries(logCounts)) {
  descriptions[name] = `Natural log of 1 plus ${count}. Compresses large counts so doubling the count does not double the feature value.`;
}
for (const [kind, label] of Object.entries({heading:'headings', paragraph:'paragraphs', list_item:'list items', table:'tables', code:'code blocks'})) {
  descriptions[`${kind}_word_fraction`] = `Word occurrences in ${label} divided by total word occurrences in the scoring view, capped at 1. Repeated words count repeatedly. These independently computed block fractions are not guaranteed to sum to 1.`;
}

export function describeFeature(rawFeature: string, missing = false) {
  const description = descriptions[rawFeature] ?? 'No description is available for this feature in the current UI.';
  return missing ? `Missingness indicator: 1 when this feature was unavailable, 0 when observed. Its weight applies to missingness, not the feature value. Underlying feature: ${description}` : description;
}

export function FeatureHelp({term, label, rawFeature, missing = false, weight}: {
  term:string; label:string; rawFeature:string; missing?:boolean; weight?:number;
}) {
  const known = weight !== undefined && Number.isFinite(weight);
  const direction = !known ? 'unavailable' : weight > 0 ? 'positive' : weight < 0 ? 'negative' : 'zero';
  const badge = !known ? 'Weight unavailable' : weight > 0 ? 'Weight +' : weight < 0 ? 'Weight −' : 'Weight 0';
  return <details className="feature-help">
    <summary><span>{label}</span> <span className={`feature-weight ${direction}`}>{badge}</span></summary>
    <div className="feature-help-body">
      <p>{describeFeature(rawFeature, missing)}</p>
      <p><strong>Fixed model weight: {known ? `${weight > 0 ? '+' : ''}${weight.toPrecision(5)}` : 'unavailable'}.</strong>{known && (weight === 0
        ? ' This term contributes nothing to the model score.'
        : ` Increasing this ${missing ? 'missingness indicator' : 'feature'} pushes the model score ${weight > 0 ? 'up' : 'down'}, holding other model inputs fixed.`)}</p>
      <p>The weight stays fixed before and after rewriting. Rewrite effect = weight × change in standardized feature value. Bar direction shows the contribution, not the weight’s sign. These are model associations, not factual quality or citation uplift.</p>
      <code>{term}</code>
    </div>
  </details>;
}
