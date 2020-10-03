// ==UserScript==
// @name         One Click Copy Image Link
// @version      0.1
// @description  Click right mouse button to copy image src to clipboard
// @author       KunoiSayami
// @homepageURL  https://github.com/KunoiSayami/Twitter-Image-Auto-Downloader
// @namespace    https://github.com/KunoiSayami/
// @match        https://twitter.com/*
// @require      https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // Reference: https://stackoverflow.com/a/5393604
    $(document).mousedown(function(event) {
        if (event.which != 3) {
            return true;
        }
        //console.log(event);
        // Reference: https://stackoverflow.com/a/9012576
        let text = $(event.target)[0].src;
        if (text !== undefined) {
            //console.log(text);
            // Reference: https://stackoverflow.com/a/13802235
            event.preventDefault();
            event.stopPropagation();
            // Reference: https://stackoverflow.com/a/30810322
            navigator.clipboard.writeText(text).then(function() {
                //console.log('Async: Copying to clipboard was successful!');
            }, function(err) {
                //console.error('Async: Could not copy text: ', err);
            });
        }
        return false;
    });

    // Reference: https://api.jquery.com/contextmenu/
    $(document).contextmenu(function(event) {
        event.preventDefault();
        //alert('success!');
        return false;
    });

})();