"use client";
import Image from "next/image";
import { useEffect, useState } from "react";

interface ApiResponse {
  message: string;
  data: number[];
}

interface QueryResult {
  rank: number;
  chunk_id: string;
  source_page: number;
  cosine_similarity: number;
  preview: string;
  full_text: string;
}

interface QueryResponse {
  query: string;
  results: Record<string, QueryResult[]>;
}

interface Stats {
  chunks: Record<string, { count: number; avg_tokens: number }>;
}

const STRATEGIES = ["fixed", "structural", "semantic"];

export default function Home() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [querying, setQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  useEffect(() => {
    fetch(`${apiUrl}/api/hello`)
      .then((res) => {
        if (!res.ok) throw new Error("Network response was not ok");
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });

    fetch(`${apiUrl}/api/stats`)
      .then((res) => res.json())
      .then(setStats)
      .catch(() => {});
  }, [apiUrl]);

  const handleQuery = async () => {
    if (!query.trim()) return;
    setQuerying(true);
    setQueryResult(null);
    try {
      const res = await fetch(`${apiUrl}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 5 }),
      });
      if (!res.ok) throw new Error("Query failed");
      const json: QueryResponse = await res.json();
      setQueryResult(json);
    } catch (err: any) {
      setQueryResult(null);
      setError(err.message);
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500 p-4">
      <main className="w-full max-w-4xl rounded-2xl bg-white/20 backdrop-blur-lg border border-white/30 p-10 shadow-2xl">
        <div className="flex items-center gap-3 mb-8">
          <Image src="/next.svg" alt="Next.js logo" width={90} height={20} className="invert" priority />
          <span className="text-white/60 text-2xl font-light">+</span>
          <span className="text-white text-xl font-semibold tracking-tight">FastAPI</span>
        </div>

        <h1 className="text-4xl font-bold text-white drop-shadow-md mb-2">
          Full Stack Demo
        </h1>
        <p className="text-white/70 mb-8 text-sm">
          Next.js frontend connected to Python FastAPI backend
        </p>

        <div className="rounded-xl bg-white/10 border border-white/20 p-6 mb-6">
          <h2 className="text-white text-lg font-semibold mb-3">API Connection</h2>
          {loading && (
            <div className="flex items-center gap-3 text-white">
              <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              <span>Connecting to FastAPI...</span>
            </div>
          )}
          {error && (
            <div className="text-red-200 bg-red-500/20 rounded-lg p-4">
              <strong>Error:</strong> {error}
              <p className="text-xs mt-1 text-red-300">Is the FastAPI server running on port 8000?</p>
            </div>
          )}
          {data && (
            <div className="text-white space-y-2">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
                <span className="text-green-300 text-sm font-medium">API Connected</span>
              </div>
              <p className="text-2xl font-semibold">{data.message}</p>
            </div>
          )}
        </div>

        {stats && (
          <div className="rounded-xl bg-white/10 border border-white/20 p-4 mb-6">
            <h3 className="text-white text-sm font-medium mb-2">Pipeline Stats</h3>
            <div className="flex gap-4 text-xs text-white/70">
              {STRATEGIES.map((s) => (
                <span key={s}>
                  {s}: {stats.chunks?.[s]?.count ?? 0} chunks
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-xl bg-white/10 border border-white/20 p-6">
          <h2 className="text-white text-lg font-semibold mb-3">RAG Semantic Search</h2>
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !querying && handleQuery()}
              placeholder="Ask a question about the document..."
              className="flex-1 px-4 py-2 rounded-lg bg-white/10 border border-white/30 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/30"
            />
            <button
              onClick={handleQuery}
              disabled={querying || !query.trim()}
              className="px-4 py-2 bg-white/20 border border-white/30 text-white rounded-lg hover:bg-white/30 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {querying ? "Searching..." : "Search"}
            </button>
          </div>

          {queryResult && (
            <div className="space-y-4">
              <p className="text-sm text-white/70 break-words">"{queryResult.query}"</p>
              {STRATEGIES.map((strategy) => (
                <div key={strategy} className="rounded-lg bg-white/5 border border-white/10 p-3">
                  <h4 className="text-white/80 font-medium text-sm mb-2 capitalize">{strategy}</h4>
                  {queryResult.results[strategy]?.length === 0 ? (
                    <p className="text-xs text-white/40">No results</p>
                  ) : (
                    <div className="space-y-2">
                      {queryResult.results[strategy]?.slice(0, 3).map((r) => (
                        <div key={r.chunk_id} className="text-xs">
                          <div className="flex justify-between text-white/60">
                            <span>#{r.rank} — page {r.source_page}</span>
                            <span>{r.cosine_similarity.toFixed(4)}</span>
                          </div>
                          <p className="text-white/80 mt-1 line-clamp-3">{r.preview}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="text-white/40 text-xs mt-6 text-center">
          FastAPI @ {apiUrl} · Next.js
        </p>
      </main>
    </div>
  );
}
