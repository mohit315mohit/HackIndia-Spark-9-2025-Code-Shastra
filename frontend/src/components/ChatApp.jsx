/* eslint-disable no-unused-vars */
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
// import ChatBox from "./ChatBox";
import ReactMarkdown from "react-markdown";
import ChatInput from "./ChatInput";

const ChatApp = () => {
  const [messages, setMessages] = useState([
    {
      text: "Hi! I'm CampusCopilot 🤖. Ask me anything about college life!",
      sender: "bot",
    },
  ]);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (input) => {
    if (!input.trim()) return;

    const userMsg = { text: input, sender: "user" };
    setMessages((prev) => [...prev, userMsg]);


    try {
      const res = await fetch("http://localhost:6969/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input }),
      });

      const data = await res.json();

      const botMsg = {
        text: "", // Start with an empty text for typewriter effect
        sender: "bot",
      };
      setMessages((prev) => [...prev, botMsg]);

      // Simulate typewriter effect
      const fullText = data.response || "Sorry, I didn’t understand that.";
      let currentText = "";
      for (let i = 0; i < fullText.length; i++) {
        await new Promise((resolve) => setTimeout(resolve, 1)); // Adjust typing speed here
        currentText += fullText[i];
        setMessages((prev) => {
          const updatedMessages = [...prev];
          updatedMessages[updatedMessages.length - 1].text = currentText;
          return updatedMessages;
        });
      }

    } catch (err) {
      console.error("Fetch error:", err);
      setMessages((prev) => [
        ...prev,
        {
          text: "Oops! Something went wrong. Please try again.",
          sender: "bot",
        },
      ]);
  
    }
  };

  return (
    <>
      <div className="h-screen w-full relative overflow-hidden bg-[#0A0F25] font-sans">
        {/* Background Blurs */}
        <div className="absolute inset-0 opacity-10"></div>
        <div className="absolute top-0 right-0 w-80 h-80 bg-blue-500 rounded-full filter blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-600 rounded-full filter blur-3xl"></div>
        <div className="absolute top-1/3 left-1/4 w-64 h-64 bg-pink-500 rounded-full filter blur-3xl"></div>

        {/* Decorative Elements */}
        <div className="absolute top-10 left-10 w-20 h-20 border-2 border-blue-400 rounded-full opacity-20"></div>
        <div className="absolute bottom-20 right-10 w-32 h-32 border-2 border-purple-400 rounded-full opacity-20"></div>
        <div className="absolute top-1/2 left-5 w-3 h-3 bg-blue-400 rounded-full animate-pulse"></div>
        <div className="absolute top-1/4 right-10 w-3 h-3 bg-purple-400 rounded-full animate-pulse"></div>
        <div className="absolute top-3/4 right-1/3 w-3 h-3 bg-pink-400 rounded-full animate-pulse"></div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="h-screen ml-auto p-6 pt-[5rem] z-10 relative pl-72"
        >
          {/* Title */}
          <motion.div
            className="flex items-center justify-center mb-6"
            initial={{ y: -20 }}
            animate={{ y: 0 }}
            transition={{ type: "spring", stiffness: 300 }}
          >
            <div className="bg-gradient-to-r from-purple-600 to-blue-500 p-4 rounded-full mr-3 shadow-lg shadow-purple-500/30">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-6 w-6 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                />
              </svg>
            </div>
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-500 to-blue-400 drop-shadow-md">
              CampusCopilot
            </h1>
          </motion.div>

          {/* Chat Box */}
          <motion.div
            className="bg-gray-900/70 backdrop-blur-sm rounded-2xl shadow-xl p-6 mb-4 h-[27rem] overflow-y-auto border border-gray-700/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <AnimatePresence>
              {messages.map((msg, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`mb-4 flex ${
                    msg.sender === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  {msg.sender === "bot" && (
                    <div className="h-8 w-8 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 flex items-center justify-center mr-2 shadow-md">
                      <span className="text-xs font-bold text-white">AI</span>
                    </div>
                  )}
                  <div
                    className={`px-4 py-3 rounded-2xl max-w-4xl whitespace-pre-line shadow-md ${
                      msg.sender === "user"
                        ? "bg-gradient-to-r from-purple-600 to-blue-500 text-white rounded-br-none shadow-purple-500/20"
                        : "bg-gray-800/90 text-gray-100 rounded-bl-none"
                    }`}
                  >
                    <ReactMarkdown>{msg.text}</ReactMarkdown>
                  </div>
                  {msg.sender === "user" && (
                    <div className="h-8 w-8 rounded-full bg-gradient-to-r from-pink-500 to-purple-500 flex items-center justify-center ml-2 shadow-md">
                      <span className="text-xs font-bold text-white">You</span>
                    </div>
                  )}
                </motion.div>
              ))}

              <div ref={messagesEndRef} />
            </AnimatePresence>
          </motion.div>

          {/* Input */}
          <motion.div
            className="absolute bottom-10 left-1/6 w-[79.8%]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
          >
            <ChatInput onSend={handleSend} />
          </motion.div>
        </motion.div>
      </div>
    </>
  );
};

export default ChatApp;
