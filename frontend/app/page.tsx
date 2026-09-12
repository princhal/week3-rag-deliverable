"use client";
import Image from "next/image";
import { useEffect, useState } from "react";

interface ApiResponse {
  message: string;
  data: number[];
}

export default function Home() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/api/hello")
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
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500 p-4">
      <main className="w-full max-w-2xl rounded-2xl bg-white/20 backdrop-blur-lg border border-white/30 p-10 shadow-2xl">
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

        <div className="rounded-xl bg-white/10 border border-white/20 p-6">
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
            <div className="text-white space-y-4">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
                <span className="text-green-300 text-sm font-medium">API Connected</span>
              </div>
              <p className="text-2xl font-semibold">{data.message}</p>
              <div className="flex gap-3 mt-2">
                {data.data.map((num) => (
                  <span
                    key={num}
                    className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 border border-white/30 text-white font-bold text-lg"
                  >
                    {num}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <p className="text-white/40 text-xs mt-6 text-center">
          FastAPI @ localhost:8000 · Next.js @ localhost:3000
        </p>
      </main>
    </div>
  );
}
