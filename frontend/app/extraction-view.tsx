'use client';

export type ParsedBlock = {
  block_id: string;
  parent_id: string | null;
  type: string;
  text: string;
  heading_level: number | null;
  mapping_status: string;
  source_locator: Record<string, unknown> | null;
  links: { text: string; target: string; resolved_target: string }[];
  table: null | { caption: string; rows: number; cells: { row: number; column: number; text: string; is_header: boolean; rowspan: number; colspan: number }[] };
};
export type Chunk = { chunk_id: string; block_ids: string[]; heading_path: { text: string }[]; markdown: string; characters: number; oversized: boolean };
export type Extraction = { method: string | null; status: string; quality_flags: string[]; reasons: string[]; upstream_revision: string; policy: string };

export function ExtractionStatus({ extraction }: { extraction: Extraction }) {
  return <div className="extraction-status" role="status">
    <strong>{extraction.method === 'conservative_dom' ? 'Conservative DOM extraction' : extraction.method === 'markdown_text' ? 'Native Markdown / text extraction' : 'Source needs attention'}</strong>
    <span>{extraction.status === 'selected' ? 'Parsed' : extraction.status === 'needs_review' ? 'Review required' : 'Insufficient source content'}</span>
    <p>{extraction.quality_flags.length ? extraction.quality_flags.map(flag => flag.replaceAll('_', ' ')).join(' · ') : 'Structured blocks and source references retained.'}</p>
    {extraction.status !== 'selected' && <p>{extraction.reasons.join(' ')}</p>}
  </div>;
}

export function StructuredBlocks({ blocks }: { blocks: ParsedBlock[] }) {
  return <>{blocks.map(block => <div className="block" key={block.block_id}>
    <span className="block-kind">{block.type === 'heading' ? `h${block.heading_level}` : block.type}</span>
    <div className="block-content">
      <small>{block.block_id}{block.parent_id ? ` · Parent: ${block.parent_id}` : ''} · {block.mapping_status.replaceAll('_', ' ')}</small>
      {block.type === 'code' ? <pre>{block.text}</pre> : block.table ? <div className="source-table"><table>
        {block.table.caption && <caption>{block.table.caption}</caption>}
        <tbody>{Array.from({ length: block.table.rows }, (_, row) => <tr key={row}>{block.table!.cells.filter(cell => cell.row === row).map(cell => cell.is_header
          ? <th key={cell.column} rowSpan={cell.rowspan} colSpan={cell.colspan}>{cell.text}</th>
          : <td key={cell.column} rowSpan={cell.rowspan} colSpan={cell.colspan}>{cell.text}</td>)}</tr>)}</tbody>
      </table></div> : block.text ? <p>{block.text}</p> : <p className="source-help">{block.type} container</p>}
      {block.source_locator && <details><summary>Source location</summary><pre>{JSON.stringify(block.source_locator, null, 2)}</pre></details>}
      {block.links.length > 0 && <details><summary>{block.links.length} source links</summary>{block.links.map((link, index) => <p key={index}>{link.text} · {link.resolved_target}</p>)}</details>}
    </div>
  </div>)}</>;
}

export function StructuredChunks({ chunks }: { chunks: Chunk[] }) {
  return <>{chunks.map(chunk => <div className="chunk" key={chunk.chunk_id}>
    <strong>{chunk.heading_path.map(heading => heading.text).join(' / ') || 'Page introduction'}</strong>
    <p className="source-help">{chunk.characters.toLocaleString()} characters · {chunk.block_ids.length} blocks{chunk.oversized ? ' · Oversized: retained in full' : ''}</p>
    <small>{chunk.chunk_id}</small>
    <details><summary>View chunk and source blocks</summary><p>{chunk.block_ids.join(', ')}</p><pre>{chunk.markdown}</pre></details>
  </div>)}</>;
}
