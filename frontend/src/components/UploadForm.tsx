import { useState, useEffect, useRef } from "react";

export default function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>("Waiting for upload...");
  const [summary, setSummary] = useState<string>("");
  const [pdf, setPdf] = useState<string>("");
  const [progress, setProgress] = useState<number>(0);
  const [taskId] = useState(() => crypto.randomUUID());
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    connectWebSocket();
    return () => socketRef.current?.close();
  }, [taskId]);

  const connectWebSocket = () => {
    socketRef.current = new WebSocket(`ws://127.0.0.1:8000/ws/${taskId}`);

    socketRef.current.onopen = () => {
      setStatus("✅ WebSocket connected.");
    };

    socketRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("WebSocket received:", data);
        setStatus((prevStatus) => prevStatus !== data.status ? data.status : prevStatus);
        if (data.progress !== undefined) {
          setProgress(data.progress);
        }
      } catch (error) {
        console.error("Error parsing WebSocket message:", error);
      }
    };

    socketRef.current.onerror = (error) => {
      console.error("WebSocket error:", error);
      setStatus("⚠️ WebSocket connection error!");
    };

    socketRef.current.onclose = (event) => {
      console.warn("WebSocket closed:", event.code, event.reason);
      setStatus("🔄 Reconnecting WebSocket...");
      setTimeout(connectWebSocket, 3000); // Auto-reconnect
    };
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setProgress(0);
    setStatus("🔄 Connecting WebSocket...");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("task_id", taskId);

    try {
      const response = await fetch("http://127.0.0.1:8000/process_video/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! Status: ${response.status} - ${errorText}`);
      }

      const data = await response.json();
      setSummary(data.summary);
      setPdf(data.pdf);
      setStatus("✅ Processing complete!");
      setProgress(100);
    } catch (error) {
      setStatus("❌ Upload failed!");
      console.error("Upload Error:", error);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-6">
      <h1 className="text-3xl font-bold mb-6">Upload a Video for Transcription</h1>

      <form onSubmit={handleUpload} className="p-6 bg-white rounded-lg shadow-md w-96">
        <input
          type="file"
          accept="video/mp4,video/mkv,video/avi"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="mb-4 p-2 border rounded w-full"
        />

        <button
          type="submit"
          disabled={!file}
          className={`w-full px-4 py-2 text-white rounded ${
            file ? "bg-blue-500 hover:bg-blue-600" : "bg-gray-400"
          }`}
        >
          Upload
        </button>
      </form>

      <div className="mt-4 p-4 bg-white rounded-lg shadow-md w-96 text-center">
        <p className="text-lg font-semibold">Status:</p>
        <p className="text-gray-700">{status}</p>
      </div>

      {progress > 0 && (
        <div className="w-96 mt-4 bg-gray-200 rounded-full h-4">
          <div
            className="bg-blue-500 h-4 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      )}

      {summary && (
        <div className="mt-6 p-4 bg-white rounded-lg shadow-md w-96">
          <h2 className="text-lg font-bold">Summary</h2>
          <p className="text-gray-700">{summary}</p>
        </div>
      )}

      {pdf && (
        <div className="mt-6 p-4 bg-white rounded-lg shadow-md w-96">
          <h2 className="text-lg font-bold">Download Summary PDF</h2>
          <a
            href={`http://127.0.0.1:8000${pdf}`}
            target="_blank"
            rel="noopener noreferrer"
            className="block mt-4 px-4 py-2 bg-green-500 text-white rounded text-center hover:bg-green-600"
          >
            📄 Download PDF
          </a>
        </div>
      )}
    </div>
  );
}
