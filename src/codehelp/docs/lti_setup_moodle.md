title:  Moodle LTI Setup for CodeHelp
summary:  Step-by-step instructions for creating an LTI connection to CodeHelp from a Moodle course.


# Moodle LTI Setup for CodeHelp

To set up your Moodle course to use CodeHelp, you need to register CodeHelp as a new "External Tool" in Moodle.

At some schools, this may require your IT staff's help if they have restricted this functionality in your Moodle site.
If at any step of these instructions an option shown here is not available in your course, that may be why.
If adding CodeHelp as an External Tool is not possible at your institution, you can use the <a href="manual_class_creation">manual class creation process</a> instead.

1. First, add a new Activity to your course, and select the "External Tool" type:

  <p class="hasimg">
  <img class="docimg" alt='Screenshot: Adding an External Tool in Moodle' src='/static/moodle_LTI_01_add_activity.svg'>
  </p>

2. In the screen for adding the new External Tool, create a new tool configuration using the "+" button next to the "preconfigured tool" select box:

  <p class="hasimg">
  <img class="docimg" alt='Screenshot: External tool creation screen, highlighting the "+" button' src='/static/moodle_LTI_02_add_LTI_tool.svg'>
  </p>

3. In the configuration form you reach, configure the tool with the following values:
  * Tool name: CodeHelp (this is how you will identify it in the list of tools available to you)
  * Tool URL: https://codehelp.app/lti/
  * Consumer Key and Shared Secret: (these will be provided to you by CodeHelp when you register to integrate with your LMS)
  * Privacy &gt; Share launcher's name with tool: Always
  * Privacy &gt; Share launcher's email with tool: Always
  * Privacy &gt; Accept grades from the tool: Never
  * Privacy &gt; Force SSL: Checked
  * All other fields can be left with their default values.

  <p class="hasimg">
  <img class="docimg" alt='"Add App" form in Moodle settings' src='/static/moodle_LTI_03_tool_configuration.svg'>
  </p>

4. Upon saving that configuration, you should be returned to the previous screen, with the new "CodeHelp" tool now selected in the "Preconfigured tool" setting.  You can give the activity a name, description, etc. and add it to your course.  This will add a link to your course that anyone (student, TA, or instructor) can use to access CodeHelp and authenticate automatically.  Anyone registered with the course as a TA or instructor will have access to CodeHelp's instructor interfaces.
