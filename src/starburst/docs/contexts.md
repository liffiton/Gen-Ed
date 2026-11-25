---
title:  Using Contexts
summary:  Guidance and suggestions on how to use contexts in your class.
category:  Using Starburst
---

# Using Contexts

When responding to a query, a large language model (LLM) only has access to the information contained in that single query -- it will make assumptions about anything not included.
It won't know anything about your course, your students, or the material they are studying unless it is explicitly told.
Furthermore, students do not always know what details they should provide to get the most helpful response.
**Contexts** let you as the instructor provide one or more sets of information to be provided along with students' queries.
As the name suggests, you can think of each one as a "context" within which a student is seeking help.

A context has two areas:

- **Details** are shown to students when they select a context.  Use them to describe the course, the material being studied, or the assignment students are working on.
- **Additional instructions** are sent to the LLM but are never shown to students.  This area contains:
  - **General guidance** --- instructions for how the LLM should respond in this context.
  - **Terms and concepts to avoid** --- a list of terms or concepts the LLM should not use or mention at all.

Only the context's **name** is required; the three content fields are all optional.  You can use markdown headings, lists, and paragraphs in **Details** and **General guidance** to organize larger contexts.

Contexts are very flexible, with many ways to configure them in a class.
Here are some possibilities, some of which could be combined:

1) **No context defined.**
   - Not recommended.  The LLM will only know what is written by the student in each query.
   - This may be acceptable for a demonstration of the tool or for a very general audience with a wide range of unpredictable needs.
1) **A single, default context.**
   - The minimum recommended.
   - If the context in which students are working is consistent throughout the course, this can work.
   - You could also use a single context that you update throughout the course term.
1) **One context for each module or unit** in the course.
   - For example, you could define a separate context for each unit of a survey course.
1) **Separate contexts for all assignments,** projects, or their separate sections.
   - In the **Details** for each context, you can include all relevant specifications or instructions from the assignment.
   - Without defined contexts, many students will copy and paste the complete assignment instructions into their query, and they often included irrelevant details from it as well.
1) **A "conceptual question" context.**
   - For students to ask questions that are not tied to any particular assignment, it is best to define a separate context for that if all of the other contexts are tied to specific assignments.

## What to Include

**Name** --- Context names are used by the students to select a context when there are multiple available, and the chosen context's name is included in the query sent to the LLM as well.  It should be short, clear, and descriptive.  Even with nothing else defined in a context, a name like "Cell Biology" will provide some information for the LLM to use.  If there is only one context for the class, however, it is recommended you name it "Default" and fill in other details.

**Details** --- Here, you can describe the context in whatever level of detail makes sense.  For a general, course-wide context, you might state the level of the course, list the topics covered, describe what background a student can be expected to have, or possibly just leave it blank.  For an assignment- or project-specific context, you can include the specifications and instructions that will be most relevant and unlikely to be assumed correctly by an LLM.  The details are also shown to students when they are writing a query, so they can confirm that they have selected the right context.

For example, in an introductory biology course:

```markdown
**Course:** Introduction to Cell Biology

Students are learning the structure and function of eukaryotic cells.
They have covered the cell membrane, organelles, and basic metabolism,
but they have not yet studied the details of DNA replication.
```

**General guidance** --- These are additional instructions for the LLM that are not shown to the students.  You might provide more details here, specific suggestions or directions, guidance on *how* to respond, or really anything else.

**Terms and concepts to avoid** --- LLMs will often suggest whatever approach or explanation is widely considered standard, but that might not be what you are expecting your students to use, especially early in a course.  This section can be used to tell the LLM to *not* mention specific terms or concepts in its response at all.  Write one term or concept per line.  These are not shown to students.

For example:

```text
oxidative phosphorylation
ATP synthase
proton gradient
```

Be specific: a broad term may prevent the model from discussing an entire topic.  Often, you won't know what to include here until you see a response use something more advanced than you expect, but then you can quickly edit the context at that point to apply to later queries.

## Availability

Every context has an availability setting.
You can make it available "Now" (immediately), scheduled to become available on a future date, or "Hidden."
This controls whether and when each context will be listed for students as an option when writing a query.
If there is only one context available, it will be used automatically, and students will not have a choice.
When multiple contexts are available, students will be able to choose from them when writing a query.  Their most recently-used context, if any, will be pre-selected for them, but they can choose another.

Generally, hiding a context is meant to simplify the choices shown to a student but not to prevent them from using a context.
When a context is "Hidden," it can still be used in a few cases:

1) If you provide a link directly to a context (see the "Link to" action in the contexts table), students who use it will be taken to an inquiry form with that context pre-selected.
1) If a student's most recent query used that context, they can still use it in their next query.
1) If a student chooses to "Retry" a query whose context is hidden, it can be used in the new query as well.

One way you might use this is to have contexts defined for every assignment or unit, keep them all hidden to avoid overloading the context choice dropdown, and then provide a link to the one relevant context directly from each assignment or unit.

## Suggestions

- Set up contexts in advance of the course starting or before making Starburst available to your students.
- Visit the inquiry chat page yourself to see how contexts can be selected and are displayed to your students.
- Monitor the responses students are getting to look for opportunities to refine contexts and improve future responses.
  - If you see a response that mentions a term or concept you don't want students to use yet, add it to the terms and concepts to avoid.
  - If you see several responses that make incorrect assumptions or interpret queries incorrectly, consider whether additional **Details** or **General guidance** could help.
- Don't overload a context.  Too much information can result in the LLM being less likely to find and use the most relevant details.  Additionally, everything included in a context adds to the length of the prompt sent to the LLM for every query, and LLM cost scales directly with prompt length.  Trying to include every possible detail that might be relevant in a context *could* make the responses worse and *will* increase the costs.

## Examples

### Names Only

Often, the only context needed is to name the subject so that students can ask questions without having to explain the setting themselves (which they often will not think to do).  If a course covers several distinct subjects, creating one context for each subject could work well.  In these cases, nothing beyond the context name is needed, and the rest could be left blank.

For example, in a course with units on several historical periods, a complete set of contexts could be:

<div class="message mb-1"><div class="message-body content p-3">
<b>Name:</b> General Questions
</div></div>
<div class="message mb-1"><div class="message-body content p-3">
<b>Name:</b> Ancient World
</div></div>
<div class="message mb-1"><div class="message-body content p-3">
<b>Name:</b> Medieval Europe
</div></div>
<div class="message"><div class="message-body content p-3">
<b>Name:</b> Early Modern Europe
</div></div>

### Additional Context

When students are learning to use a particular method, framework, or way of thinking, it is helpful to describe those expectations so that responses fit the course.

For example, in a course where students are learning to write literary analysis, the **Details** might describe the course and the current text, the hidden **General guidance** might set the teaching style, and the hidden **Terms and concepts to avoid** might rule out interpretive approaches the class has not covered yet:

<div class="message mb-1"><div class="message-body content p-3">

**Name:** Literary Analysis

**Details:** **Course:** Introduction to Literary Analysis

Students are learning to write close readings of short fiction.  They are
practicing thesis statements, textual evidence, and paragraph structure.
The current unit focuses on characterization in modernist short stories.
</div></div>
<div class="message mb-1"><div class="message-body content p-3">

**General guidance:** Ask the student to explain their interpretation and point
to evidence in the text before offering suggestions.  Do not write paragraphs
of analysis for the student; suggest a direction and ask a follow-up question.

</div></div>
<div class="message"><div class="message-body content p-3">

**Terms and concepts to avoid:**
```text
psychoanalytic criticism
deconstruction
postcolonial theory
```

</div></div>
