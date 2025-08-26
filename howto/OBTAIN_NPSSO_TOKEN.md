[new]: img/new_browser.png
[store_sign]: img/store-signin.png
[store_sso]: img/store-signin2.png
[store_auth]: img/store-signin3.png
[npsso]: img/npsso.png
[error]: img/error.png

# How to obtain the NPSSO token

1. Make sure you have the latest version of [Mozilla Firefox](https://www.mozilla.org/en-US/firefox/new/), [Google Chrome](https://www.google.com/chrome/) or the new Chromium-based [Microsoft Edge](https://www.microsoft.com/en-us/edge) browser installed before continuing.

   > It has been reported that Google Chrome version 74 experiences this issue where Sony's authorisation fails due to a CORS bug. This is why it is STRONGLY recommended to update your browsers to the latest version.

2. Open up a new browser window
   
   ![new]

3. Navigate to [https://store.playstation.com](https://store.playstation.com)

   ![store_sign]

4. Sign in to the PlayStation Store

   ![store_sso]

   ![store_auth]

5. Open a new tab and navigate to [https://ca.account.sony.com/api/v1/ssocookie](https://ca.account.sony.com/api/v1/ssocookie)

   You should see the following:

   ![npsso]

   If you see this error instead:

   ![error]
   ```JSON
   {"error":"invalid_grant","error_description":"Invalid login","error_code":20,"docs":"https://auth.api.sonyentertainmentnetwork.com/docs/","parameters":[]}
   ```

   - Switch back to the Playstation Store tab (which you should still have open). 
   - Sign out.
   - Sign back in. 
   - Switch back to the [https://ca.account.sony.com/api/v1/ssocookie](https://ca.account.sony.com/api/v1/ssocookie) tab and refresh the page (`CTRL+R` or `CTRL+F5`)

6. Copy the 64-character _NPSSO_ token without the quotes.

