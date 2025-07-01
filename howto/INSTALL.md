[timeout]: img/timeout.png
[backup1]: img/run_backup.png
[backup2]: img/run_backup2.png
[exit]: img/exit_gog.png
[plugins1]: img/plugins1.png
[plugins2]: img/plugins2.png
[plugins3]: img/plugins3.png
[connecting]: img/connecting.png
[connected]: img/connected.png
[settings]: img/settings.png
[modal]: img/connect-modal.png
[offline]: img/offline.png
[disconnected]: img/disconnected.png
[downloading]: img/downloading.png
[downloadrelease1]: img/downloadrelease1.png
[downloadrelease2]: img/downloadrelease2.png
[unpackandcopyrelease]: img/unpackandcopyrelease.png

# GOG Galaxy PlayStation Network Connector Sign-in Workaround

As of the time of writing, the Playstation Network integration plugin for GOG Galaxy 2.0 fails to sign in for many people.
After entering user credentials, users are presented with an error that `The connection to the server timed out`.

![timeout]

The cause of the timeout error has to do with a CORS error being returned during the authentication process with the PlayStation server which only seems to be occuring with the current version of the built-in GOG Galaxy browser.

It is reported that the fix for this issue is that the built-in browser needs to be updated to a newer version. GOG is supposedly aware of the issue and there is no current ETA for a fix. My guess is that there should be a fix with the next update of GOG Galaxy 2.0. 

Until a fix is released for the issue in question, a workaround has been found by `Bustacap`, which this page details out with additional steps and images.

## Workaround to Fix the Sign-in Timeout Issue

### **Backup**

The very first step I would suggest is that you backup your current Galaxy folder in case things go wrong. If you follow the steps outlined in this guide, you should be fine.

1. Open up the _Run_ box (`CTRL+R`)
2. Enter the following in the _Run_ box:
   ```
   %LocalAppData%\GOG.com
   ```
   Then hit _Ok_

   ![backup1]

3. Backup the _Galaxy_ folder.
   I backed it up just by archiving the whole folder using 7-zip.

   ![backup2]

### **Preparing The GOG PlayStation Network Plugin**

Here we will be making sure that the PlayStation Network is disconnected, and that an un-altered version of the plugin is installed.

1. Exit GOG
   
   ![exit]

2. Open up the _Run_ box (`CTRL+R`)
3. Enter the following in the _Run_ box:
   ```
   %LocalAppData%\GOG.com\Galaxy\plugins\installed\
   ```
   Then hit _Ok_

   ![plugins1]

4. If present, delete the `psn_{random-id}` folder. 
   
   ![plugins2]

5. Launch GOG.
6. Open up the `Settings => Integration` page.
   
   ![settings]

   You should see a `Connect` button for _PlayStation Network_. However, if you were previously signed into the _PlayStation Network_, you could be seeing a `Connecting` status for the connector. 

   ![connecting]

   If you have a stuck `Connecting` state:
    - Exit GOG
      
      ![exit]
    
    - Relaunch GOG
    - Navigate to the `Settings => Integrations` page.
    - If you see either `Connected` or `Offline`, then click `Disconnect`.
      
      ![connected]

      ![offline]
  
7. Ensure that you are disconnected:
   
   ![disconnected]

8. To download the PSN plugin again, click `Connect`.
   
   ![downloading]

9.  When the confirmation dialog comes up, click `Cancel`.

    ![modal]

10. Exit GOG
   
    ![exit]

### **Modifying the PlayStation Network Plug-in**

At this point, you should now have a clean version of the PSN plugin installed and disconnected. The next steps will cover manually updating the plugin with custom version.

1. Open up the _Run_ box (`CTRL+R`)
2. Enter the following in the _Run_ box:
   ```
   %LocalAppData%\GOG.com\Galaxy\plugins\installed\
   ```
   Then hit _Ok_

   ![plugins1]

3. Open the `psn_{random-id}` folder. 
   
   ![plugins2]
   
   ![plugins3]

4. Download latest release from [GitHub](https://github.com/toptaran/galaxy-integration-psn)

   Click at `Latest release` at right side block
   
   ![downloadrelease1]

   Click on `windows.zip` to download.

   ![downloadrelease2]

5. Unpack it at any folder. Follow in `windows` folder. `Select` all content (CTRL + A) and `Copy`

   ![unpackandcopyrelease]

6. Return back to plugin folder at step 3 and `Paste` here with `Replace`

7. Open GOG and connect your psn profile.

