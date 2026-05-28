import React, { useState } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { logAPI, parseAnalysis } from '../services/api';
import { LogUploadResponse, AnalysisResult } from '../types';

const UploadPage: React.FC = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<LogUploadResponse | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSuccessPopup, setShowSuccessPopup] = useState(false);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
      setUploadResult(null);
      setAnalysis(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const result = await logAPI.uploadFile(file);
      setUploadResult(result);

      // If analysis was triggered, fetch it
      if (result.analysis_id) {
        const analysisData = await logAPI.getAnalysis(result.analysis_id);
        setAnalysis(parseAnalysis(analysisData));
      }

      // Show success popup
      setShowSuccessPopup(true);

      // Auto-redirect to dashboard after 2 seconds
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Upload Log File</h1>
        <p className="text-gray-400">Upload a log file for analysis using AI-powered anomaly detection</p>
      </div>

      {/* Upload Area */}
      <div className="bg-gray-800 rounded-lg p-8 border-2 border-dashed border-gray-600 hover:border-blue-500 transition">
        <div className="flex flex-col items-center">
          <Upload className="h-12 w-12 text-gray-400 mb-4" />
          <input
            type="file"
            onChange={handleFileSelect}
            accept=".log,.txt"
            className="hidden"
            id="file-upload"
          />
          <label
            htmlFor="file-upload"
            className="cursor-pointer text-blue-400 hover:text-blue-300"
          >
            {file ? file.name : 'Click to select a log file'}
          </label>
          {file && (
            <p className="mt-2 text-sm text-gray-500">{(file.size / 1024).toFixed(2)} KB</p>
          )}
        </div>
      </div>

      {/* Upload Button */}
      {file && (
        <button
          onClick={handleUpload}
          disabled={uploading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-medium py-3 px-4 rounded-lg transition flex items-center justify-center"
        >
          {uploading ? (
            <>
              <Loader2 className="animate-spin h-5 w-5 mr-2" />
              Uploading and Analyzing...
            </>
          ) : (
            <>
              <Upload className="h-5 w-5 mr-2" />
              Upload & Analyze
            </>
          )}
        </button>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 flex items-start">
          <AlertCircle className="h-5 w-5 text-red-400 mr-3 mt-0.5" />
          <p className="text-red-300">{error}</p>
        </div>
      )}

      {/* Upload Result */}
      {uploadResult && (
        <div className="bg-green-900/50 border border-green-700 rounded-lg p-4 flex items-start">
          <CheckCircle className="h-5 w-5 text-green-400 mr-3 mt-0.5" />
          <div>
            <p className="text-green-300 font-medium">Upload successful!</p>
            <p className="text-green-400 text-sm">
              {uploadResult.entries_count} log entries processed
            </p>
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {analysis && (
        <div className="bg-gray-800 rounded-lg p-6 space-y-4">
          <h2 className="text-xl font-bold text-white flex items-center">
            <FileText className="h-6 w-6 mr-2 text-blue-400" />
            Analysis Results
          </h2>

          {/* Severity */}
          <div className={`p-4 rounded-lg ${
            analysis.severity === 'Critical' ? 'bg-red-900/50 border border-red-700' :
            analysis.severity === 'Warning' ? 'bg-yellow-900/50 border border-yellow-700' :
            'bg-green-900/50 border border-green-700'
          }`}>
            <p className={`font-semibold ${
              analysis.severity === 'Critical' ? 'text-red-300' :
              analysis.severity === 'Warning' ? 'text-yellow-300' :
              'text-green-300'
            }`}>
              Severity: {analysis.severity}
            </p>
            <p className="text-sm text-gray-400">Confidence: {(analysis.confidence_score * 100).toFixed(1)}%</p>
          </div>

          {/* Anomalies */}
          {analysis.anomalies.length > 0 && (
            <div>
              <h3 className="font-semibold text-white mb-2">Anomalies Detected</h3>
              <ul className="list-disc list-inside space-y-1 text-gray-300">
                {analysis.anomalies.map((anomaly, idx) => (
                  <li key={idx}>{anomaly}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Root Causes */}
          {analysis.root_causes.length > 0 && (
            <div>
              <h3 className="font-semibold text-white mb-2">Potential Root Causes</h3>
              <ul className="list-disc list-inside space-y-1 text-gray-300">
                {analysis.root_causes.map((cause, idx) => (
                  <li key={idx}>{cause}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Resolutions */}
          {analysis.resolutions.length > 0 && (
            <div>
              <h3 className="font-semibold text-white mb-2">Suggested Resolutions</h3>
              <ul className="list-disc list-inside space-y-1 text-gray-300">
                {analysis.resolutions.map((resolution, idx) => (
                  <li key={idx}>{resolution}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Success Popup */}
      {showSuccessPopup && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-8 max-w-md w-full mx-4 border border-green-700">
            <div className="flex items-center justify-center mb-4">
              <CheckCircle className="h-16 w-16 text-green-400" />
            </div>
            <h2 className="text-2xl font-bold text-white text-center mb-2">Upload Successful!</h2>
            <p className="text-gray-300 text-center mb-4">
              Your log file has been uploaded and analyzed successfully.
            </p>
            <p className="text-gray-400 text-center mb-6">
              {uploadResult?.entries_count} log entries processed
            </p>
            <div className="flex items-center justify-center">
              <Loader2 className="animate-spin h-5 w-5 text-blue-400 mr-2" />
              <span className="text-gray-400">Redirecting to dashboard...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadPage;
