import { useState, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import { demoCases } from "../data/cases";
import { Send, Scale, Gavel } from "lucide-react";
import { api } from "../utils/api";

export default function DualChatInterface() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const selectedCase = demoCases.find((c) => c.id === caseId);

  const [lawyerAMessages, setLawyerAMessages] = useState([]);
  const [lawyerBMessages, setLawyerBMessages] = useState([]);
  const [lawyerAInput, setLawyerAInput] = useState("");
  const [lawyerBInput, setLawyerBInput] = useState("");
  const [showJudgmentButton, setShowJudgmentButton] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(true);

  const lawyerAScrollRef = useRef(null);
  const lawyerBScrollRef = useRef(null);

  // Load existing messages on mount
  useEffect(() => {
    const loadMessages = async () => {
      try {
        const data = await api.getMessages(caseId);
        setLawyerAMessages(data.lawyerA || []);
        setLawyerBMessages(data.lawyerB || []);
      } catch (error) {
        console.error('Failed to load messages:', error);
      } finally {
        setIsLoadingMessages(false);
      }
    };
    
    loadMessages();
  }, [caseId]);

  useEffect(() => {
    if (lawyerAScrollRef.current) {
      lawyerAScrollRef.current.scrollTop = lawyerAScrollRef.current.scrollHeight;
    }
  }, [lawyerAMessages]);

  useEffect(() => {
    if (lawyerBScrollRef.current) {
      lawyerBScrollRef.current.scrollTop = lawyerBScrollRef.current.scrollHeight;
    }
  }, [lawyerBMessages]);

  // Show judgment button after both lawyers have sent at least 2 messages
  useEffect(() => {
    const lawyerACount = lawyerAMessages.filter((m) => m.role === "lawyer").length;
    const lawyerBCount = lawyerBMessages.filter((m) => m.role === "lawyer").length;
    if (lawyerACount >= 2 && lawyerBCount >= 2) {
      setShowJudgmentButton(true);
    }
  }, [lawyerAMessages, lawyerBMessages]);

  const generateAssistantResponse = (lawyerMessage, side) => {
    const responses = [
      "Consider citing precedent cases that support your argument.",
      "You may want to emphasize the legal principles of duty of care and breach.",
      "Reference relevant statutes and regulations that apply to this matter.",
      "Consider the burden of proof required for this type of claim.",
      "Highlight any contradictions in the opposing party's position.",
      "Ensure you address all elements required to establish liability.",
      "You might strengthen your argument by citing expert testimony or documentation.",
      "Consider the remedies available and what specific relief you're seeking.",
    ];
    return responses[Math.floor(Math.random() * responses.length)];
  };

  const handleLawyerASend = async () => {
    if (!lawyerAInput.trim()) return;

    const content = lawyerAInput;
    setLawyerAInput("");

    try {
      // Save lawyer message to backend
      await api.saveMessage(caseId, "A", "lawyer", content);

      const newMessage = {
        role: "lawyer",
        content: content,
        timestamp: new Date().toISOString(),
      };
      setLawyerAMessages([...lawyerAMessages, newMessage]);

      // Simulate assistant response
      setTimeout(async () => {
        const assistantContent = generateAssistantResponse(content, "A");
        
        // Save assistant message to backend
        await api.saveMessage(caseId, "A", "assistant", assistantContent);
        
        const assistantMessage = {
          role: "assistant",
          content: assistantContent,
          timestamp: new Date().toISOString(),
        };
        setLawyerAMessages((prev) => [...prev, assistantMessage]);
      }, 1000);
    } catch (error) {
      console.error('Error sending message:', error);
    }
  };

  const handleLawyerBSend = async () => {
    if (!lawyerBInput.trim()) return;

    const content = lawyerBInput;
    setLawyerBInput("");

    try {
      // Save lawyer message to backend
      await api.saveMessage(caseId, "B", "lawyer", content);

      const newMessage = {
        role: "lawyer",
        content: content,
        timestamp: new Date().toISOString(),
      };
      setLawyerBMessages([...lawyerBMessages, newMessage]);

      // Simulate assistant response
      setTimeout(async () => {
        const assistantContent = generateAssistantResponse(content, "B");
        
        // Save assistant message to backend
        await api.saveMessage(caseId, "B", "assistant", assistantContent);
        
        const assistantMessage = {
          role: "assistant",
          content: assistantContent,
          timestamp: new Date().toISOString(),
        };
        setLawyerBMessages((prev) => [...prev, assistantMessage]);
      }, 1000);
    } catch (error) {
      console.error('Error sending message:', error);
    }
  };

  const handleRequestJudgment = () => {
    navigate(`/judgment/${caseId}`);
  };

  if (!selectedCase) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <p className="text-white">Case not found</p>
      </div>
    );
  }

  if (isLoadingMessages) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-amber-400 border-t-transparent mb-4"></div>
          <p className="text-white">Loading debate...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-slate-900 flex flex-col">
      {/* Header */}
      <div className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="flex items-center justify-between max-w-[1800px] mx-auto">
          <div className="flex items-center gap-3">
            <Scale className="w-6 h-6 text-amber-400" />
            <div>
              <h1 className="text-xl text-white">{selectedCase.title}</h1>
              <p className="text-sm text-slate-400">{selectedCase.category}</p>
            </div>
          </div>
          {showJudgmentButton && (
            <button
              onClick={handleRequestJudgment}
              className="flex items-center gap-2 px-6 py-3 bg-amber-500 hover:bg-amber-600 text-slate-900 rounded-lg transition-colors"
            >
              <Gavel className="w-5 h-5" />
              Request Final Judgment
            </button>
          )}
        </div>
      </div>

      {/* Split Chat Interface */}
      <div className="flex-1 flex overflow-hidden">
        {/* Lawyer A Side */}
        <div className="flex-1 flex flex-col border-r border-slate-700">
          <div className="bg-blue-600 px-6 py-3">
            <h2 className="text-white text-lg">Lawyer A - Plaintiff</h2>
          </div>
          
          {/* Chat Messages */}
          <div ref={lawyerAScrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
            {lawyerAMessages.length === 0 && (
              <div className="text-center text-slate-500 mt-8">
                Start presenting your arguments...
              </div>
            )}
            {lawyerAMessages.map((message, idx) => (
              <div
                key={idx}
                className={`flex ${message.role === "lawyer" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg p-4 ${
                    message.role === "lawyer"
                      ? "bg-blue-600 text-white"
                      : "bg-slate-700 text-slate-100"
                  }`}
                >
                  <div className="text-xs opacity-70 mb-1">
                    {message.role === "lawyer" ? "Lawyer A" : "Legal Assistant"}
                  </div>
                  <p>{message.content}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Input Area */}
          <div className="p-4 bg-slate-800 border-t border-slate-700">
            <div className="flex gap-2">
              <input
                type="text"
                value={lawyerAInput}
                onChange={(e) => setLawyerAInput(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleLawyerASend()}
                placeholder="Present your argument..."
                className="flex-1 bg-slate-700 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleLawyerASend}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>

        {/* Lawyer B Side */}
        <div className="flex-1 flex flex-col">
          <div className="bg-purple-600 px-6 py-3">
            <h2 className="text-white text-lg">Lawyer B - Defendant</h2>
          </div>
          
          {/* Chat Messages */}
          <div ref={lawyerBScrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
            {lawyerBMessages.length === 0 && (
              <div className="text-center text-slate-500 mt-8">
                Start presenting your arguments...
              </div>
            )}
            {lawyerBMessages.map((message, idx) => (
              <div
                key={idx}
                className={`flex ${message.role === "lawyer" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg p-4 ${
                    message.role === "lawyer"
                      ? "bg-purple-600 text-white"
                      : "bg-slate-700 text-slate-100"
                  }`}
                >
                  <div className="text-xs opacity-70 mb-1">
                    {message.role === "lawyer" ? "Lawyer B" : "Legal Assistant"}
                  </div>
                  <p>{message.content}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Input Area */}
          <div className="p-4 bg-slate-800 border-t border-slate-700">
            <div className="flex gap-2">
              <input
                type="text"
                value={lawyerBInput}
                onChange={(e) => setLawyerBInput(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleLawyerBSend()}
                placeholder="Present your argument..."
                className="flex-1 bg-slate-700 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <button
                onClick={handleLawyerBSend}
                className="px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}