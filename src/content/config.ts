import { defineCollection, z } from "astro:content";

const products = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    decathlonId: z.string(),
    price: z.number(),
    oldPrice: z.number().optional(),
    image: z.string().url(),
    category: z.string(),
    sport: z.string(),
    description: z.string(),
    specs: z.record(z.string()).optional(),
    rating: z.number().min(0).max(5).optional(),
    reviewCount: z.number().int().nonnegative().optional(),
    available: z.boolean().default(true),
    affiliateUrl: z.string().url(),
  })
});

const categories = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    sport: z.string(),
    icon: z.string().optional(),
  })
});

const guides = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    sport: z.string().optional(),
    icon: z.string().optional(),
  })
});

export const collections = { products, categories, guides };
