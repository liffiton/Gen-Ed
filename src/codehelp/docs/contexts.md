---
title:  Using Contexts
summary:  Guidance and suggestions on how to use contexts in your class.
---

# Using Contexts

When responding to a query, a large language model (LLM) only has access to the information contained in that single query -- it will make assumptions about anything not included.
It won't know anything about your course or the problems students are working on unless it is explicitly told.
Furthermore, students do not always know what details they should provide to get the most helpful response.
**Contexts** let you as the instructor provide one or more sets of information to be provided along with students' queries.
As the name suggests, you can think of each one as a "context" within which a student is seeking help.

A context contains:
- A descriptive name
- *[optional]* The languages, libraries, and/or frameworks that students are learning or using in the context.
- *[optional]* Free-form written details for the context.
- *[optional]* A set of keywords and concepts you want the responses to *not* include.  This is commonly used to prevent a response from suggesting a technique or tool that is more advanced than the course is expecting in this context.

Contexts are very flexible, with many ways to configure them in a class.
Here are some possibilities, some of which could be combined:

1) **No context defined.**
   - Not recommended.  The LLM will only know what is written by the student in each query.
   - This may be acceptable for a demonstration of the tool or for a very general audience with a wide range of unpredictable needs.
1) **A single, default context.**
   - The minimum recommended.
   - If the context in which students are working is consistent throughout the course, this can work.
   - You could also use a single context that you update throughout the course term.
1) **One context for each module** in the course.
   - For example, you could define a separate context for each language used in a programming languages course.
1) **Separate contexts for all assignments,** projects, or their separate sections.
   - In the "details" section of each context, you can include all relevant specifications or instructions from the assignment.
   - Without defined contexts, many students will copy and paste the complete assignment instructions into their query, and they often included irrelevant details from it as well.
1) **A "conceptual question" context.**
   - For students to ask questions that are not tied to any particular code or programming environment, it is best to define a separate context for that if all of the other contexts are oriented toward coding.

## What to Include

**Name** --- Context names are used by the students to select a context when there are multiple available, and the chosen context's name is included in the query sent to the LLM as well.  It should be short, clear, and descriptive.  Even with nothing else defined in a context, a name like "Python" will provide some information for the LLM to use.  If there is only one context for the class, however, it is recommended you name it "Default" and fill in other details.

**Environment and Tools** --- List all languages, frameworks, libraries, and tools that could be relevant to a student's query in this context.  For example, in a web development class, a student could ask, "How do I make a route respond only to POST requests?"  If the context specifies the web framework being used in the course, the LLM's response will be much more helpful.  Whatever you enter here will be shown to the student for reference when they are writing a query.

**Details** --- Here, you can describe the context in whatever level of detail makes sense.  For a general, course-wide context, you might state the level of the course, describe what background a student can be expected to have, or possibly just leave it blank.  For an assignment- or project-specific context, you can include the specifications and instructions that will be most relevant and unlikely to be assumed correctly by an LLM.  The details section of a context will also be shown to students when writing a query.

**Keywords to Avoid** --- LLMs will often suggest whatever approach to solving a problem is widely considered a best practice, but that might not be what you are expecting your students to do, especially in a lower-level class.  This section can be used to tell the LLM to *not* use any of the listed keywords or concepts in its response.  Often, you won't know what to include here until you see a response use something more advanced than you expect, but then you can quickly edit the context at that point to apply to later queries.  The keywords here will *not* be shown to students.

## Availability

Every context has an availability setting.
You can make it available "Now" (immediately), scheduled to become available on a future date, or "Hidden."
This controls whether and when each context will be listed for students as an option when writing a query.
If there is only one context available, it will be used automatically, and students will not have a choice.
When multiple contexts are available, students will be able to choose from them when writing a query.  Their most recently-used context, if any, will be pre-selected for them, but they can choose another.

Generally, hiding a context is meant to simplify the choices shown to a student but not to prevent them from using a context.
When a context is "Hidden," it can still be used in a few cases:

1) If you provide a link directly to a context (see the "Link to" action in the contexts table), students who use it will be taken to a help form with that context pre-selected.
1) If a student's most recent query used that context, they can still use it in their next query.
1) If a student chooses to "Retry" a query whose context is hidden, it can be used in the new query as well.

One way you might use this is to have contexts defined for every assignment or exercise, keep them all hidden to avoid overloading the context choice dropdown in the help form, and then provide a link to the one relevant context directly from each assignment or exercise.

## Suggestions

- Set up contexts in advance of the course starting or before making CodeHelp available to your students.
- Visit the [help form page](/help/) yourself to see how contexts can be selected and are displayed to your students.
- Monitor the responses students are getting to look for opportunities to refine contexts and improve future responses.
  - If you see a response that suggests something you don't want students to use, add it to the avoid set.
  - If you see several responses that make incorrect assumptions or interpret queries incorrectly, consider whether additional context could help.
- Don't overload a context.  Too much information can result in the LLM being less likely to find and use the most relevant details.  Additionally, everything included in a context adds to the length of the prompt sent to the LLM for every query, and LLM cost scales directly with prompt length.  Trying to include every possible detail that might be relevant in a context *could* make the responses worse and *will* increase the costs.

## Examples

**Names Only:** Often, the only context needed is to name the programming language so that students can ask questions like "How do I [x]?" without having to provide that context themselves (which they often will not think to do).  If a course uses multiple languages (such as in a web development course, perhaps), then creating one context for each language could work well.  In these cases, nothing beyond the context name is needed, and the rest could be left blank.

For example, in a web development course using Python and Flask on the back-end, a complete set of contexts could be:

<div class="message mb-1"><div class="message-body content p-3">
<b>Name:</b> Conceptual Question
</div></div>
<div class="message mb-1"><div class="message-body content p-3">
<b>Name:</b> HTML
</div></div>
<div class="message mb-1"><div class="message-body content p-3">
<b>Name:</b> CSS
</div></div>
<div class="message mb-1"><div class="message-body content p-3">
<b>Name:</b> JavaScript
</div></div>
<div class="message"><div class="message-body content p-3">
<b>Name:</b> Python + Flask
</div></div>

**Additional Context:** When students are first learning a new programming language, we often want them to use the language in a particular way to emphasize certain features or ways of thinking.  In these cases, it is helpful to provide that context so that responses fit those expectations.

For example, in a class introducing functional programming using the OCaml language ('utop' is an OCaml REPL students might use):

<div class="message"><div class="message-body content p-3">

**Name:** OCaml

**Environment and tools:** Ocaml; utop

**Details:** Students learning OCaml, probably as their first major introduction to functional programming.  The focus is on functional programming and recursion, so iteration and loops are not covered or used.

**Keywords to Avoid:** for loop; while loop
</div></div>
