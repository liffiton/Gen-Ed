---
title:  Moodle LTI Setup for CodeHelp
summary:  Step-by-step instructions for creating an LTI connection to CodeHelp from a Moodle course.
---

# Moodle LTI Setup for CodeHelp

To set up your Moodle course to use CodeHelp, you need to add CodeHelp as a new "External Tool" in Moodle.

At some schools, this may require your IT staff's help if they have restricted this functionality in your Moodle site.
If at any step of these instructions an option shown here is not available in your course, that may be why.
If adding CodeHelp as an External Tool is not possible at your institution, you can use the <a href="manual_class_creation">manual class creation process</a> instead.

1. First, add a new Activity to your course, and select the "External Tool" type:

  <p class="hasimg">
  <img class="docimg" alt='Screenshot: Adding an External Tool in Moodle' src='/static/moodle_LTI_01_add_activity.svg'>
  </p>

2. In the screen for adding the new External Tool, configure the tool with the following values (you will need to press "Show more..." to reach some of them):
  * **Activity name:** CodeHelp (or whatever you want it to be named in your course)
  * **Secure tool URL:** https://codehelp.app/lti/
    * The warning it shows you saying "Tool configuration not found..." is not a problem.
  * **Launch container:** New window
  * **Consumer Key and Shared Secret:** (these will be provided to you by CodeHelp when you register to integrate with your LMS)
  * **Privacy &gt; Accept grades from the tool:** Unchecked
  * All other fields can be left with their default values.

  <p class="hasimg">
  <img class="docimg" alt='Screenshot: External tool creation screen, highlighting settings to change' src='/static/moodle_LTI_02_tool_configuration.svg'>
  </p>

3. Saving the activity will add a link to your course that anyone (student, TA, or instructor) can use to access CodeHelp and authenticate automatically.  Anyone registered with the course as a TA or instructor will have access to CodeHelp's instructor interfaces.
