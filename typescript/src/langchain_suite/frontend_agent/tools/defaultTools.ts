/**
 * Default domain tools for the TypeScript Frontend Agent Showcase.
 *
 * Provides:
 * 1. `getCurrentTime`: Timezone-aware date and time lookup.
 * 2. `getRandomQuote`: Curated multi-category quotes for inspiration & wisdom.
 */

import { tool } from "@langchain/core/tools";
import { z } from "zod";

export const QUOTE_REPOSITORY: Record<string, Array<{ quote: string; author: string }>> = {
  technology: [
    {
      quote: "Any sufficiently advanced technology is indistinguishable from magic.",
      author: "Arthur C. Clarke",
    },
    {
      quote: "Simplicity is prerequisite for reliability.",
      author: "Edsger W. Dijkstra",
    },
    {
      quote: "The best way to predict the future is to invent it.",
      author: "Alan Kay",
    },
    {
      quote: "Software is eating the world, but AI is eating software.",
      author: "Marc Andreessen (Adapted)",
    },
  ],
  philosophy: [
    {
      quote: "We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
      author: "Will Durant (on Aristotle)",
    },
    {
      quote: "The unexamined life is not worth living.",
      author: "Socrates",
    },
    {
      quote: "He who has a why to live can bear almost any how.",
      author: "Friedrich Nietzsche",
    },
  ],
  motivation: [
    {
      quote: "It always seems impossible until it's done.",
      author: "Nelson Mandela",
    },
    {
      quote: "Do what you can, with what you have, where you are.",
      author: "Theodore Roosevelt",
    },
    {
      quote: "Action is the foundational key to all success.",
      author: "Pablo Picasso",
    },
  ],
  science: [
    {
      quote: "Somewhere, something incredible is waiting to be known.",
      author: "Carl Sagan",
    },
    {
      quote: "Science is a way of thinking much more than it is a body of knowledge.",
      author: "Carl Sagan",
    },
  ],
};

export const getCurrentTime = tool(
  async ({ timezone = "UTC" }: { timezone?: string }) => {
    const tz = (timezone || "UTC").trim();
    try {
      const now = new Date();
      const formatter = new Intl.DateTimeFormat("en-US", {
        timeZone: tz,
        dateStyle: "full",
        timeStyle: "long",
      });
      return `Current Time in ${tz}: ${formatter.format(now)} (ISO: ${now.toISOString()})`;
    } catch {
      // Fallback to UTC if timezone invalid
      const now = new Date();
      const formatter = new Intl.DateTimeFormat("en-US", {
        timeZone: "UTC",
        dateStyle: "full",
        timeStyle: "long",
      });
      return `Note: Unrecognized timezone '${tz}', defaulted to UTC. Current Time: ${formatter.format(now)}`;
    }
  },
  {
    name: "get_current_time",
    description: "Return the current date, time, weekday, and offset for a specified IANA timezone (e.g. 'UTC', 'Europe/Berlin', 'America/New_York', 'Asia/Tokyo').",
    schema: z.object({
      timezone: z
        .string()
        .optional()
        .default("UTC")
        .describe("Standard IANA timezone string, e.g. 'UTC', 'Europe/Berlin', 'Asia/Tokyo'"),
    }),
  }
);

export const getRandomQuote = tool(
  async ({ category = "general" }: { category?: string }) => {
    const cat = (category || "general").trim().toLowerCase();

    if (QUOTE_REPOSITORY[cat] && QUOTE_REPOSITORY[cat].length > 0) {
      const quotes = QUOTE_REPOSITORY[cat];
      const picked = quotes[Math.floor(Math.random() * quotes.length)];
      return `"${picked.quote}" — ${picked.author} [${cat.charAt(0).toUpperCase() + cat.slice(1)}]`;
    }

    // Default to any category
    const allQuotes: Array<{ quote: string; author: string; catName: string }> = [];
    for (const [cName, list] of Object.entries(QUOTE_REPOSITORY)) {
      for (const item of list) {
        allQuotes.push({ ...item, catName: cName });
      }
    }
    const picked = allQuotes[Math.floor(Math.random() * allQuotes.length)];
    return `"${picked.quote}" — ${picked.author} [${picked.catName.charAt(0).toUpperCase() + picked.catName.slice(1)}]`;
  },
  {
    name: "get_random_quote",
    description: "Return an inspiring quote from a given thematic category: 'technology', 'philosophy', 'motivation', 'science', or 'general'.",
    schema: z.object({
      category: z
        .string()
        .optional()
        .default("general")
        .describe("The topic or category for the quote: 'technology', 'philosophy', 'motivation', 'science', or 'general'"),
    }),
  }
);

