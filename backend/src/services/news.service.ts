import { config } from "../config/config.js";

export type DevNewsItem = {
  title: string;
  summary: string;
  source: string;
  date: string | null;
  link: string;
};

type NewsSource = {
  name: string;
  url: string;
};

const defaultSources: NewsSource[] = [
  { name: "Python.org", url: "https://www.python.org/blogs/rss/" },
  { name: "TypeScript Blog", url: "https://devblogs.microsoft.com/typescript/feed/" },
  { name: "Node.js Blog", url: "https://nodejs.org/en/feed/blog.xml" },
  { name: "V8 Blog", url: "https://v8.dev/blog.atom" },
  { name: "MDN Blog", url: "https://developer.mozilla.org/en-US/blog/rss.xml" },
  { name: "TC39", url: "https://github.com/tc39/proposals/releases.atom" }
];

let cache: {
  fetchedAt: number;
  items: DevNewsItem[];
  errors: string[];
} | null = null;

function decodeEntities(input: string): string {
  return input
    .replace(/<!\[CDATA\[(.*?)\]\]>/gs, "$1")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/<[^>]*>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function firstMatch(block: string, patterns: RegExp[]): string | null {
  for (const pattern of patterns) {
    const match = block.match(pattern);
    if (match?.[1]) {
      return decodeEntities(match[1]);
    }
  }

  return null;
}

function parseFeed(xml: string, source: NewsSource): DevNewsItem[] {
  const blocks = [
    ...xml.matchAll(/<item[\s\S]*?<\/item>/gi),
    ...xml.matchAll(/<entry[\s\S]*?<\/entry>/gi)
  ].map(match => match[0]);

  return blocks
    .map(block => {
      const title = firstMatch(block, [/<title[^>]*>([\s\S]*?)<\/title>/i]) ?? "Ohne Titel";
      const summary = firstMatch(block, [
        /<description[^>]*>([\s\S]*?)<\/description>/i,
        /<summary[^>]*>([\s\S]*?)<\/summary>/i,
        /<content[^>]*>([\s\S]*?)<\/content>/i
      ]) ?? "Keine Kurzfassung verfügbar.";
      const date = firstMatch(block, [
        /<pubDate[^>]*>([\s\S]*?)<\/pubDate>/i,
        /<updated[^>]*>([\s\S]*?)<\/updated>/i,
        /<published[^>]*>([\s\S]*?)<\/published>/i
      ]);
      const hrefLink = block.match(/<link[^>]*href=["']([^"']+)["'][^>]*>/i)?.[1];
      const textLink = firstMatch(block, [/<link[^>]*>([\s\S]*?)<\/link>/i]);
      const link = decodeEntities(hrefLink ?? textLink ?? source.url);

      return {
        title,
        summary: summary.length > 280 ? `${summary.slice(0, 277)}...` : summary,
        source: source.name,
        date,
        link
      } satisfies DevNewsItem;
    })
    .filter(item => Boolean(item.title));
}

function sortByDateDesc(items: DevNewsItem[]): DevNewsItem[] {
  return [...items].sort((a, b) => {
    const left = a.date ? Date.parse(a.date) : 0;
    const right = b.date ? Date.parse(b.date) : 0;
    return right - left;
  });
}

export async function getDevNews(forceRefresh = false) {
  const now = Date.now();

  if (
    !forceRefresh &&
    cache &&
    now - cache.fetchedAt < config.newsCacheTtlSeconds * 1000
  ) {
    return {
      fromCache: true,
      fetchedAt: new Date(cache.fetchedAt).toISOString(),
      items: cache.items,
      errors: cache.errors
    };
  }

  const items: DevNewsItem[] = [];
  const errors: string[] = [];

  await Promise.all(
    defaultSources.map(async source => {
      try {
        const response = await fetch(source.url, {
          headers: {
            Accept: "application/rss+xml, application/atom+xml, application/xml, text/xml"
          }
        });

        if (!response.ok) {
          errors.push(`${source.name}: HTTP ${response.status}`);
          return;
        }

        const xml = await response.text();
        items.push(...parseFeed(xml, source));
      } catch (error) {
        errors.push(`${source.name}: ${error instanceof Error ? error.message : String(error)}`);
      }
    })
  );

  const sorted = sortByDateDesc(items).slice(0, config.newsMaxItems);

  cache = {
    fetchedAt: now,
    items: sorted,
    errors
  };

  return {
    fromCache: false,
    fetchedAt: new Date(now).toISOString(),
    items: sorted,
    errors
  };
}

export function getNewsSources(): NewsSource[] {
  return defaultSources;
}
