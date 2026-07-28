"use client";

import { ExchangeRateCard } from "@/components/currency";
import {
  useFrontendTool,
  useRenderTool,
  CopilotSidebar,
  CopilotChatMessageView,
  CopilotChatAssistantMessage,
} from "@copilotkit/react-core/v2";
import { useA2UI, A2UIRenderer } from "@copilotkit/a2ui-renderer";
import React, { useState, useEffect } from "react";
import { z } from "zod";

function normalizeA2UIJson(parsed: any) {
  if (!parsed) return parsed;

  let components: any[] = [];
  if (Array.isArray(parsed)) {
    components = parsed;
  } else if (parsed && Array.isArray(parsed.components)) {
    components = parsed.components;
  } else if (parsed && parsed.updateComponents && Array.isArray(parsed.updateComponents.components)) {
    components = parsed.updateComponents.components;
  } else if (parsed && parsed.message && Array.isArray(parsed.message.components)) {
    components = parsed.message.components;
  } else {
    return parsed;
  }

  const normalized: any[] = [];
  components.forEach((c: any) => {
    const norm: any = { ...c };
    if (!norm.type && norm.component) {
      norm.type = norm.component;
    }
    if (!norm.props) {
      norm.props = {};
    }
    if (norm.text !== undefined && norm.props.value === undefined) {
      norm.props.value = norm.text;
    }
    if (norm.variant !== undefined && norm.props.variant === undefined) {
      norm.props.variant = norm.variant;
    }
    if (norm.title !== undefined && norm.props.title === undefined) {
      norm.props.title = norm.title;
    }
    if (norm.child !== undefined && norm.props.child === undefined) {
      norm.props.child = norm.child;
    }
    if (norm.children !== undefined && norm.props.children === undefined) {
      norm.props.children = norm.children;
    }
    if (norm.type === 'Card' && !norm.props.title) {
      norm.props.title = norm.title || "💵 Conversion Result";
    }
    normalized.push(norm);
  });

  const result = {
    version: parsed.version || "0.9",
  } as any;

  if (parsed.updateComponents) {
    result.updateComponents = {
      ...parsed.updateComponents,
      components: normalized,
    };
  } else if (parsed.createSurface) {
    result.createSurface = {
      ...parsed.createSurface,
    };
  } else {
    result.updateComponents = {
      surfaceId: parsed.surfaceId || "currency_agent",
      components: normalized,
    };
  }

  return result;
}

function parseA2UIContent(text: string) {
  let cleanText = text;
  let jsonStr: string | null = null;
  let surfaceId = "currency_agent"; // default surface ID

  // 1. Cut off streaming XML/JSON from cleanText so it doesn't leak during streaming
  const xmlStartIndex = text.indexOf("<a2ui-json>");
  if (xmlStartIndex !== -1) {
    cleanText = text.substring(0, xmlStartIndex);
    const xmlMatch = text.match(/<a2ui-json>([\s\S]*?)<\/a2ui-json>/);
    if (xmlMatch) {
      jsonStr = xmlMatch[1];
    }
  } else {
    // Check if there is a raw JSON block starting with { and containing "version": "v0.9"
    const jsonStartIndex = text.search(/\{[\s\S]*?"version"\s*:\s*"v0.9"/);
    if (jsonStartIndex !== -1) {
      cleanText = text.substring(0, jsonStartIndex);
      const jsonMatch = text.match(/(\{[\s\S]*?"version"\s*:\s*"v0.9"[\s\S]*?\})/);
      if (jsonMatch) {
        jsonStr = jsonMatch[1];
      }
    }
  }

  let parsed: any = null;
  if (jsonStr) {
    try {
      const rawParsed = JSON.parse(jsonStr.trim());
      parsed = normalizeA2UIJson(rawParsed);
      if (parsed.updateComponents?.surfaceId) {
        surfaceId = parsed.updateComponents.surfaceId;
      } else if (parsed.createSurface?.surfaceId) {
        surfaceId = parsed.createSurface.surfaceId;
      }
    } catch (e) {
      // JSON is not yet complete/valid
    }
  }

  return { cleanText, parsed, surfaceId };
}


const A2UIContainer = ({ parsedJson, surfaceId }: { parsedJson: any; surfaceId: string }) => {
  const { processMessages, getSurface } = useA2UI();

  useEffect(() => {
    if (parsedJson) {
      const messagesToProcess = [];
      // Synthesize createSurface if the surface does not exist yet in A2UI store
      if (parsedJson.updateComponents && surfaceId && !getSurface(surfaceId)) {
        messagesToProcess.push({
          version: "0.9",
          createSurface: {
            surfaceId: surfaceId,
            catalogId: "https://a2ui.org/specification/v0_9/basic_catalog.json"
          }
        });
      }
      messagesToProcess.push(parsedJson);
      processMessages(messagesToProcess);
    }
  }, [parsedJson, surfaceId, processMessages, getSurface]);

  return (
    <div className="mt-3 w-full">
      <A2UIRenderer surfaceId={surfaceId} />
    </div>
  );
};


const CustomMarkdownRenderer = ({ content, ...props }: any) => {
  const { cleanText, parsed, surfaceId } = parseA2UIContent(content);
  return (
    <div className="flex flex-col gap-2 w-full">
      <CopilotChatAssistantMessage.MarkdownRenderer
        {...props}
        content={cleanText}
      />
      {parsed && surfaceId && (
        <A2UIContainer parsedJson={parsed} surfaceId={surfaceId} />
      )}
    </div>
  );
};

const CustomAssistantMessage = (props: any) => {
  return (
    <CopilotChatAssistantMessage
      {...props}
      markdownRenderer={CustomMarkdownRenderer}
    />
  );
};

const CustomMessageView = (props: any) => {
  return (
    <CopilotChatMessageView
      {...props}
      assistantMessage={CustomAssistantMessage}
    />
  );
};

const Sidebar = CopilotSidebar as any;

export default function CopilotKitPage() {
  const [themeColor, setThemeColor] = useState("#10b981"); // Mint green primary theme

  // 🪁 Frontend Actions
  useFrontendTool({
    name: "setThemeColor",
    description: "Set the theme color of the workspace.",
    parameters: z.object({
      themeColor: z.string().describe("The theme color to set. Make sure to pick nice colors."),
    }),
    async handler({ themeColor }) {
      setThemeColor(themeColor);
    },
  });

  return (
    <main
      style={
        { "--copilot-kit-primary-color": themeColor } as React.CSSProperties
      }
    >
      <Sidebar
        defaultOpen={true}
        labels={{
          title: "Currency Intelligence Assistant",
          initial: "👋 Hi! I can help you convert currencies and look up exchange rates. Try asking for a conversion below!",
        } as any}
        suggestions={[
          {
            title: "Convert USD to EUR",
            message: "How much is 250 USD in EUR?",
          },
          {
            title: "Compare USD to GBP",
            message: "What is the exchange rate for USD to GBP?",
          },
          {
            title: "Convert CAD to USD",
            message: "Can you convert 1500 CAD to USD?",
          },
          {
            title: "Latest Rates",
            message: "Get the current exchange rate for USD to JPY.",
          },
        ]}
        messageView={CustomMessageView}
      />
      <YourMainContent themeColor={themeColor} setThemeColor={setThemeColor} />
    </main>
  );
}

CustomMessageView.Cursor = CopilotChatMessageView.Cursor;

function YourMainContent({
  themeColor,
  setThemeColor,
}: {
  themeColor: string;
  setThemeColor: (color: string) => void;
}) {
  // 🪁 Generative UI: Renders the ExchangeRateCard dynamically during agent tool calls
  useRenderTool(
    {
      name: "get_exchange_rate",
      render: ({ parameters, result }: any) => {
        const from = (parameters as any)?.currency_from || "USD";
        const to = (parameters as any)?.currency_to || "EUR";
        const rate = (result as any)?.rates?.[to] || (result as any)?.rates?.[to.toUpperCase()];
        const date = (result as any)?.date;

        return (
          <ExchangeRateCard
            currencyFrom={from}
            currencyTo={to}
            rate={rate}
            date={date}
            themeColor={themeColor}
          />
        );
      },
    } as any,

    [themeColor],
  );

  return (
    <div
      style={{ backgroundColor: "#0f172a" }} // Matches deep dark-theme
      className="h-screen flex justify-center items-center flex-col transition-colors duration-300 px-6 text-center"
    >
      <div className="max-w-md bg-slate-800/80 border border-slate-700 p-8 rounded-2xl shadow-2xl backdrop-blur-md">
        <span className="text-5xl mb-4 block">💵</span>
        <h1 className="text-3xl font-extrabold text-white tracking-tight mb-2">
          Currency Intellect
        </h1>
        <p className="text-slate-400 text-sm mb-6">
          Generative UI Workspace powered by CopilotKit and Google ADK. Ask the assistant to query rates.
        </p>
        <div className="flex justify-center gap-2">
          <button 
            onClick={() => setThemeColor("#10b981")} 
            className="w-8 h-8 rounded-full border-2 border-white/20 bg-emerald-500" 
          />
          <button 
            onClick={() => setThemeColor("#3b82f6")} 
            className="w-8 h-8 rounded-full border-2 border-white/20 bg-blue-500" 
          />
          <button 
            onClick={() => setThemeColor("#ec4899")} 
            className="w-8 h-8 rounded-full border-2 border-white/20 bg-pink-500" 
          />
        </div>
      </div>
    </div>
  );
}

