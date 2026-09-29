/**
 * The design system's status families (docs/design/aia-design-system-brief.md
 * §4.3): working, waiting on a person, waiting on the world, failed, done, and
 * nothing to say. 18.6.6 painted the first three with one "warn" class; that is
 * the naive design the brief names, so here they are three tones.
 */
export type Tone = "running" | "you" | "world" | "fault" | "done" | "neutral";
