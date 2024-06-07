---
title:  Canvas LTI Setup for CodeHelp
summary:  Step-by-step instructions for creating an LTI connection to CodeHelp from a Canvas course.
---

# Canvas LTI Setup for CodeHelp

To set up your Canvas course to use CodeHelp, you need to register CodeHelp as a new "App" in Canvas.

At some schools, this may require your IT staff's help if they have restricted this functionality in your Canvas site.
If at any step of these instructions an option shown here is not available in your course, that may be why.
If adding CodeHelp as an App is not possible at your institution, you can use the <a href="manual_class_creation">manual class creation process</a> instead.

1. First, go to the course settings, find the Settings page for Apps, and if you aren't already at the App configurations page, choose "View App Configurations":

  <p class="hasimg">
  <img class="docimg" alt='"Apps" page in Canvas settings' src='/static/canvas_LTI_01_settings.svg'>
  </p>

2. On the App configurations page, press the "+ App" button:

  <p class="hasimg">
  <img class="docimg" alt='"External Apps" page in Canvas settings, highlighting the "+ App" button' src='/static/canvas_LTI_02_add_app_button.svg'>
  </p>

3. In the form that pops up, configure the application with the following values:
  * **Configuration Type:** By URL
  * **Name:** "CodeHelp" (this is how it will show up in the course navigation menu and in the list of apps available to you)
  * **Consumer Key** and **Shared Secret** will be provided to you by CodeHelp when you register to integrate with your LMS.
  * **Config URL:** https://codehelp.app/lti/config.xml

  <p class="hasimg">
  <img class="docimg" alt='"Add App" form in Canvas settings' src='/static/canvas_LTI_03_add_app_form.svg'>
  </p>

4. By default, CodeHelp will now show up as an item in the course navigation menu (on the left of each course page).
   You can reorder it in that menu or hide it in the "Navigation" tab of the course settings.
   Anyone (student, TA, or instructor) can use this link to access CodeHelp and authenticate automatically.
   Anyone registered with the course as a TA or instructor will have access to CodeHelp's instructor interfaces.

5. **Optional:** If you want to add CodeHelp as an item to a module in your course, select "External Tool" as the type when adding the new item, and locate "CodeHelp" in the list of applications shown.

  <p class="hasimg">
  <img class="docimg" alt='Adding an item to a Canvas Module, highlighting how to add CodeHelp as an External Tool' src='/static/canvas_LTI_04_add_item.svg'>
  </p>
