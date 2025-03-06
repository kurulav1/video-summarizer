import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { FiUploadCloud, FiCheckCircle, FiFileText } from "react-icons/fi";

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

    socketRef.current.onopen = () => setStatus("✅ WebSocket connected.");
    socketRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setStatus((prev) => (prev !== data.status ? data.status : prev));
        if (data.progress !== undefined) setProgress(data.progress);
      } catch (error) {
        console.error("Error parsing WebSocket message:", error);
      }
    };

    socketRef.current.onerror = (error) => {
      console.error("WebSocket error:", error);
      setStatus("⚠️ WebSocket connection error!");
    };

    socketRef.current.onclose = () => {
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
    <div className="flex items-center justify-center min-h-screen w-full bg-gradient-to-br from-blue-500 via-purple-600 to-pink-500 p-6">
      <div className="w-full max-w-2xl p-8 bg-white rounded-3xl shadow-2xl flex flex-col gap-8 mx-auto">

        {/* Title Box */}
        <div className="p-6 bg-gray-50 border border-gray-300 rounded-2xl shadow-md text-center">
          <motion.h1
            className="text-3xl font-bold text-gray-800"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            Upload a Video for Transcription
          </motion.h1>
        </div>

        {/* Upload Box */}
        <div className="p-6 bg-gray-100 border border-gray-300 rounded-2xl shadow-md">
          <form onSubmit={handleUpload} className="space-y-6">
            <motion.label
              htmlFor="file-upload"
              className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-gray-400 rounded-2xl cursor-pointer hover:bg-gray-200 transition-all bg-white shadow-md"
              whileHover={{ scale: 1.05 }}
            >
              <FiUploadCloud className="text-blue-500 text-6xl mb-3" />
              <p className="text-lg font-semibold text-gray-700">
                Click to upload or drag & drop a video
              </p>
              <input
                id="file-upload"
                type="file"
                accept="video/mp4,video/mkv,video/avi"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="hidden"
              />
            </motion.label>

            {file && (
              <motion.p
                className="text-center text-gray-700 font-semibold bg-gray-200 p-3 rounded-xl"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                Selected: {file.name}
              </motion.p>
            )}

            <button
              type="submit"
              disabled={!file}
              className={`w-full py-3 rounded-xl font-semibold transition-all ${
                file
                  ? "bg-blue-600 text-white hover:bg-blue-700 shadow-md"
                  : "bg-gray-400 text-gray-700 cursor-not-allowed"
              }`}
            >
              Upload
            </button>
          </form>
        </div>

        {/* Status Box */}
        <div className="p-4 bg-blue-100 border border-blue-300 rounded-2xl shadow-md text-gray-800 text-center">
          <p className="text-lg font-semibold">Status:</p>
          <p className="text-gray-700">{status}</p>
        </div>

        {/* Progress Bar */}
        {progress > 0 && (
          <div className="w-full bg-gray-300 rounded-full h-5 overflow-hidden shadow-md">
            <motion.div
              className="bg-blue-500 h-full"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        )}

        {/* Summary Box */}
        {summary && (
          <div className="p-6 bg-green-100 border border-green-300 rounded-2xl shadow-md text-gray-900">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <FiFileText className="text-gray-700" /> Summary
            </h2>
            <p className="text-gray-800">{summary}</p>
          </div>
        )}

        {/* PDF Download Box */}
        {pdf && (
          <div className="p-6 bg-yellow-100 border border-yellow-300 rounded-2xl shadow-md text-gray-900 text-center">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <FiCheckCircle className="text-gray-700" /> Download Summary PDF
            </h2>
            <a
              href={`http://127.0.0.1:8000${pdf}`}
              target="_blank"
              rel="noopener noreferrer"
              className="block mt-4 px-6 py-3 bg-green-600 text-white rounded-lg text-center hover:bg-green-700 transition-all shadow-lg"
            >
              📄 Download PDF
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
