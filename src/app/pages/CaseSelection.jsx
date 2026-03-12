import { useState } from "react";
import { useNavigate } from "react-router";
import { demoCases } from "../data/cases";
import { Scale, ChevronRight } from "lucide-react";

export default function CaseSelection() {
  const navigate = useNavigate();
  const [selectedCase, setSelectedCase] = useState(null);

  const handleStartDebate = () => {
    if (selectedCase) {
      navigate(`/debate/${selectedCase}`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Scale className="w-12 h-12 text-amber-400" />
            <h1 className="text-4xl text-white">AI Judge System</h1>
          </div>
          <p className="text-slate-300 text-lg">
            Select a demo case to begin the legal debate
          </p>
        </div>

        {/* Case Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {demoCases.map((demoCase) => (
            <div
              key={demoCase.id}
              onClick={() => setSelectedCase(demoCase.id)}
              className={`bg-slate-800 rounded-lg p-6 cursor-pointer transition-all border-2 ${
                selectedCase === demoCase.id
                  ? "border-amber-400 shadow-lg shadow-amber-400/20"
                  : "border-slate-700 hover:border-slate-600"
              }`}
            >
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-xl text-white">{demoCase.title}</h3>
                <span
                  className={`text-xs px-3 py-1 rounded-full ${
                    demoCase.complexity === "High"
                      ? "bg-red-500/20 text-red-300"
                      : demoCase.complexity === "Medium"
                      ? "bg-yellow-500/20 text-yellow-300"
                      : "bg-green-500/20 text-green-300"
                  }`}
                >
                  {demoCase.complexity}
                </span>
              </div>
              <p className="text-slate-400 mb-4">{demoCase.description}</p>
              <div className="flex items-center gap-2">
                <span className="text-sm px-3 py-1 bg-slate-700 text-slate-300 rounded">
                  {demoCase.category}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Start Button */}
        <div className="flex justify-center">
          <button
            onClick={handleStartDebate}
            disabled={!selectedCase}
            className={`flex items-center gap-2 px-8 py-4 rounded-lg text-lg transition-all ${
              selectedCase
                ? "bg-amber-500 hover:bg-amber-600 text-slate-900 shadow-lg shadow-amber-500/30"
                : "bg-slate-700 text-slate-500 cursor-not-allowed"
            }`}
          >
            Start Legal Debate
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
