---
title:  Canvas LTI Setup for Starburst
summary:  Step-by-step instructions for creating an LTI connection to Starburst from a Canvas course.
---

# Canvas LTI Setup for Starburst

To set up your Canvas course to use Starburst, you need to register Starburst as a new "App" in Canvas.

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
  * **Name:** "Starburst" (this is how it will show up in the course navigation menu and in the list of apps available to you)
  * **Consumer Key** and **Shared Secret:** (I will share these with you directly)
  * **Config URL:** https://strbrst.xyz/lti/config.xml

  <p class="hasimg">
  <img class="docimg" alt='"Add App" form in Canvas settings' src='/static/canvas_LTI_03_add_app_form.svg'>
  </p>

4. By default, Starburst will now show up as an item in the course navigation menu (on the left of each course page).
   You can reorder it in that menu or hide it in the "Navigation" tab of the course settings.
   Anyone (student, TA, or instructor) can use this link to access Starburst and authenticate automatically.
   Anyone registered with the course as a TA or instructor will have access to Starburst's instructor interfaces.

5. **Optional:** If you want to add Starburst as an item to a module in your course, select "External Tool" as the type when adding the new item, and locate "Starburst" in the list of applications shown.
