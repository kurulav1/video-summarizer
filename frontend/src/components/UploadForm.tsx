import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";

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
      setStatus("🔄 Reconnecting WebSocket...");
      setTimeout(connectWebSocket, 3000);
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
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-blue-100 to-blue-300 p-6">
      <motion.h1 className="text-4xl font-bold mb-8 text-gray-800" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>Upload a Video for transcription</motion.h1>
      <form onSubmit={handleUpload} className="p-6 bg-white rounded-lg shadow-lg w-96">
        <input
          type="file"
          accept="video/mp4,video/mkv,video/avi"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="mb-4 p-3 border rounded w-full text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={!file}
          className={`w-full px-4 py-2 text-white font-semibold rounded transition-all ${file ? "bg-blue-600 hover:bg-blue-700" : "bg-gray-400 cursor-not-allowed"}`}
        >Upload</button>
      </form>

      <div className="mt-4 p-4 bg-white rounded-lg shadow-md w-96 text-center">
        <p className="text-lg font-semibold text-gray-700">Status:</p>
        <p className="text-gray-600">{status}</p>
      </div>

      {progress > 0 && (
        <div className="w-96 mt-4 bg-gray-200 rounded-full h-4 overflow-hidden">
          <motion.div
            className="bg-blue-500 h-4"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5 }}
          ></motion.div>
        </div>
      )}

      {summary && (
        <motion.div className="mt-6 p-4 bg-white rounded-lg shadow-md w-96" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <h2 className="text-lg font-bold text-gray-800">Summary</h2>
          <p className="text-gray-700">{summary}</p>
        </motion.div>
      )}

      {pdf && (
        <motion.div className="mt-6 p-4 bg-white rounded-lg shadow-md w-96" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <h2 className="text-lg font-bold text-gray-800">Download Summary PDF</h2>
          <a
            href={`http://127.0.0.1:8000${pdf}`}
            target="_blank"
            rel="noopener noreferrer"
            className="block mt-4 px-4 py-2 bg-green-500 text-white rounded text-center hover:bg-green-600 transition-all"
          >📄 Download PDF</a>
        </motion.div>
      )}
    </div>
  );
}
