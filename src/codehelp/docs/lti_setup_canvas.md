# Canvas LTI Setup for CodeHelp

To set up your Canvas course to use CodeHelp, you need to register CodeHelp as a new "App" in Canvas.
At some schools, this may require your IT staff's help if they have restricted this functionality in your Canvas site.
If at any step of these instructions an option shown here is not available in your course, that may be why.

  1. First, find the Settings page for Apps, and if you aren't already at the App configurations page, choose "View App Configurations":
  <p class="hasimg">
  <img class="docimg" alt='"Apps" page in Canvas settings' src='/static/canvas_LTI_01_settings.svg'>
  </p>
  2. On the App configurations page, press the "+ App" button:
  <p class="hasimg">
  <img class="docimg" alt='"External Apps" page in Canvas settings, highlighting the "+ App" button' src='/static/canvas_LTI_02_add_app_button.svg'>
  </p>
  3. In the form that pops up, configure the application with the following values:
     * Configuration Type: Manual Entry
     * Name: "CodeHelp" (this is how you will identify it in the list of apps available to you)
     * Consumer Key and Shared Secret: (these will be provided to you by CodeHelp when you register to integrate with your LMS)
     * Launch URL: https://codehelp.app/lti/
     * Privacy: E-Mail Only
     * All other fields can be left blank.
  <p class="hasimg">
  <img class="docimg" alt='"Add App" form in Canvas settings' src='/static/canvas_LTI_03_add_app_form.svg'>
  </p>
  4. Finally, add an item to a module in your course, select "External Tool" as the type, and locate "CodeHelp" in the list of applications shown.  This will add a link to your course that anyone (student, TA, or instructor) can use to access CodeHelp and authenticate automatically.  Anyone registered with the course as a TA or instructor will have access to CodeHelp's instructor interfaces.
  <p class="hasimg">
  <img class="docimg" alt='Adding an item to a Canvas Module, highlighting how to add CodeHelp as an External Tool' src='/static/canvas_LTI_04_add_item.svg'>
  </p>
