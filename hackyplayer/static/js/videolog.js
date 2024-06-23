var framerate = 50

function bpp () {
    // Button play pause
    video = document.getElementById("video1")
    if (video.paused) {
        video.play()
    } else {
        video.pause()
    }
}
function bff (frames=1) {
    // Button Frame Forward
    document.getElementById("video1").currentTime = document.getElementById("video1").currentTime + frames/framerate
}

function bfb (frames=1) {
    // Button Frame Back
    document.getElementById("video1").currentTime = document.getElementById("video1").currentTime - frames/framerate
}

function bmi() {
    // Button Mark In
    document.getElementById("intc").value = seconds_to_timestamp(document.getElementById("video1").currentTime)
}

function bmo() {
    // Button Mark Out
    document.getElementById("outtc").value = seconds_to_timestamp(document.getElementById("video1").currentTime)
}

function bgi() {
    // Button Go In
    snap_to_timestamp(document.getElementById("intc"))
}

function bgo() {
    // Button Go Out
    snap_to_timestamp(document.getElementById("outtc"))
}

function seconds_to_timestamp (seconds) {
    // Get the number of frames
    var tot_frames = Math.round(seconds*framerate)

    // Extract number of hours/mins/secs/frames
    var hours = Math.floor(tot_frames/(framerate*60*60)) % 60
    var mins = Math.floor(tot_frames/(framerate*60)) % 60
    var secs = Math.floor(tot_frames/framerate) % 60
    var frames = Math.floor(tot_frames % framerate)

    var ret_string = hours.toString().padStart(2, "0") + ":" + mins.toString().padStart(2, "0") + ":" + secs.toString().padStart(2, "0") + ":" + frames.toString().padStart(2, "0")
    return ret_string
}

function tc_focus (ele) {
    ele.value = ""
}

function tc_focus_off (ele) {
    ele.value = seconds_to_timestamp(document.getElementById("video1").currentTime)
}

function timestamp_to_seconds (timestamp) {
    var time_array = timestamp.padStart(8, "0").match(/(.{2})(.{2})(.{2})(.{2})/)
    var hours = parseInt(time_array[1])
    var mins = parseInt(time_array[2])
    if (mins > 59){
        mins = 59
    }
    var secs = parseInt(time_array[3])
    if (secs > 59) {
        secs = 59
    }
    var frames = parseInt(time_array[4])
    if (frames > framerate){
        frames = framerate
    }

    var tot_frames = hours*60*60*framerate + mins*60*framerate + secs*framerate + frames

    return tot_frames/framerate
}

function enter_timecode(ele) {
    if(event.key === 'Enter'){
        snap_to_timestamp(ele)
        ele.value = ''
        ele.blur()
    }
}

function show_help() {
    if (document.getElementById("instructions").style.display != "block") {
        document.getElementById("instructions").style.display = "block"
    } else {
        document.getElementById("instructions").style.display = "none"
    }
}

function snap_to_timestamp (ele) {
    var time_match = ele.value.split(':').join('').match(/([\-\+])?(\d{1,8})/)
    if (time_match[1] == '+'){
        var new_time = document.getElementById("video1").currentTime + timestamp_to_seconds(time_match[2])
    } else if (time_match[1] == "-"){
        var new_time = document.getElementById("video1").currentTime - timestamp_to_seconds(time_match[2])
    } else {
        var new_time = timestamp_to_seconds(time_match[2])
    }
    document.getElementById("video1").currentTime = new_time
}

function updateTC(timestamp) {
    var frames = seconds_to_timestamp(timestamp)
    document.getElementById("current_tc").value = frames
};

function checkKey(e) {
    e = e || window.event;

    // Don't do controls if a text input field or main video
    const nopropElements = [
        document.getElementById("presenter"),
        document.getElementById("title"),
        document.getElementById("video1"),
        document.getElementById("talkid")
    ]
    if (nopropElements.indexOf(document.activeElement) != -1){
        return
    }

    const nums = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "+", "-"]
    if (e.key == 'ArrowLeft') {
        bfb()
    } else if (e.key == 'ArrowRight') {
        bff()
    } else if(e.keyCode == '32') {
        // space
        document.getElementById("inputtc").blur()
        video = document.getElementById("video1")
        if (video.paused) {
            video.play()
        } else {
            video.pause()
        }
        if (e.target == document.body){
            e.preventDefault();
        }
    } else if(e.key == 'i') {
        bmi()
    } else if(e.key == 'o') {
        bmo()
    } else if(nums.includes(e.key)) {
        document.getElementById("inputtc").focus()
    } else if(e.key == "Escape") {
        document.getElementById("inputtc").blur()
    }
}

function beginUpdatingTC(ele) {
    const frameCallback = (now, meta) => {
        updateTC(meta.mediaTime)
        ele.requestVideoFrameCallback(frameCallback)
    }
    ele.requestVideoFrameCallback(frameCallback)
    if (!('requestVideoFrameCallback' in HTMLVideoElement.prototype) || ('_rvfcpolyfillmap' in HTMLVideoElement.prototype)) {
        console.info("requestVideoFrameCallback is not available or is polyfilled, added seeked listener to update TC")
        ele.addEventListener("seeked", (ev) => {
            updateTC(ele.currentTime)
        })
    }
}

document.addEventListener("DOMContentLoaded", (ev) => {
    beginUpdatingTC(document.getElementById("video1"))
})

document.onkeydown = checkKey;

function get_shuttle() {
    let deviceFilter = { vendorId: 0x0b33, productId: 0x0030 };
    let requestParams = { filters: [deviceFilter] };
    let outputReportId = 0x01;
    let outputReport = new Uint8Array([42]);

    function handleConnectedDevice(e) {
    console.log("Device connected: " + e.device.productName);
    }

    function handleDisconnectedDevice(e) {
    console.log("Device disconnected: " + e.device.productName);
    }

    prev_data = 0
    scrub_wheel = 0
    setInterval(scrub_via_wheel,300);

    function scrub_via_wheel(){
        if (scrub_wheel > 0 && scrub_wheel < 127) {
            bff((scrub_wheel)*5)
        } else if (scrub_wheel > 128 && scrub_wheel < 256) {
            bfb((256-scrub_wheel)*5)
        }
    }

    function handleInputReport(e) {
        data = new Uint8Array(e.data.buffer)
        scrub_wheel = data[0]
        if (data[1] > prev_data[1]) {
            bff()
        } else if (data[1] < prev_data[1]) {
            bfb()
        }
        if (data[4] == 32){
            bmi()
        } else if (data[4] == 64){
            bmo()
        }
        if (data[3] == 16) {
            bgi()
        } else if (data[4] == 1) {
            bgo()
        } else if (data[3] == 64) {
            document.getElementById("video1").pause()
        } else if (data[3] == 128) {
            document.getElementById("video1").play()
        }
        console.log(data);
        console.log(prev_data);
        prev_data = data
    }

    navigator.hid.addEventListener("connect", handleConnectedDevice);
    navigator.hid.addEventListener("disconnect", handleDisconnectedDevice);

    navigator.hid.requestDevice(requestParams).then((devices) => {
        if (devices.length == 0) return;
        devices.forEach((device) => {
            device.open().then()
            console.log("Opened device: " + device.productName);
            device.addEventListener("inputreport", handleInputReport);
            device.sendReport(outputReportId, outputReport).then(() => {
            console.log("Sent output report " + outputReportId);
            setInterval(scrub_via_wheel,20);
            });
        });
    });
}

function send_to_renderer(){

    var data = new FormData();
    data.append('start_tc', document.getElementById("intc").value);
    data.append('end_tc', document.getElementById("outtc").value);
    data.append('presenter', document.getElementById("presenter").value);
    data.append('title', document.getElementById("title").value);
    data.append('video', document.getElementById("video_id").value);
    data.append('talkid', document.getElementById("talkid").value);

    document.getElementById("intc").classList.remove('invalid')
    document.getElementById("outtc").classList.remove('invalid')
    document.getElementById("presenter").classList.remove('invalid')
    document.getElementById("title").classList.remove('invalid')
    document.getElementById("talkid").classList.remove('invalid')

    // Validation
    var valid = true;
    if (!data.get('start_tc')){
        setTimeout(function() {document.getElementById("intc").classList.add('invalid')}, 100)
        valid = false
    } if (!data.get('end_tc')) {
        setTimeout(function() {document.getElementById("outtc").classList.add('invalid')}, 100)
        valid = false
    } if (data.get('start_tc') && data.get('end_tc') && timestamp_to_seconds(data.get('start_tc').replace(/\:/g,'')) >= timestamp_to_seconds(data.get('end_tc').replace(/\:/g,''))){
        setTimeout(function() {document.getElementById("intc").classList.add('invalid')}, 100)
        setTimeout(function() {document.getElementById("outtc").classList.add('invalid')}, 100)
        valid = false
    } if (!data.get('presenter')) {
        setTimeout(function() {document.getElementById("presenter").classList.add('invalid')}, 100)
        valid = false
    } if (!data.get('title')){
        setTimeout(function() {document.getElementById("title").classList.add('invalid')}, 100)
        valid = false
    } if (!data.get('talkid')){
        setTimeout(function() {document.getElementById("talkid").classList.add('invalid')}, 100)
        valid = false
    }

    if (valid) {
        // All good - send video for processing!
        var xhttp = new XMLHttpRequest();

        xhttp.onreadystatechange = function() {
            if (this.readyState == 4 && this.status == 200) {
            document.getElementById("infopopup").innerHTML = "New job ID: " + JSON.parse(xhttp.responseText)['result_id'];
            document.getElementById("infopopup").classList.remove('fadeIn')
            setTimeout(function() {document.getElementById("infopopup").classList.add('fadeIn')}, 100)
            }
        };

        xhttp.open("POST", "/api/v1/build", true);
        xhttp.send(data);
    }
}

function talk_select(e) {
    var talkdata = JSON.parse(document.getElementById('talkdata').textContent);
    if (e.value == -1) {
        document.getElementById('talkid').value = ""
        document.getElementById('talkid').readOnly = false;
        document.getElementById('talkid').classList.remove('readonly')
        document.getElementById('title').value = ""
        document.getElementById('title').readOnly = false;
        document.getElementById('title').classList.remove('readonly')
        document.getElementById('presenter').value = ""
        document.getElementById('presenter').readOnly = false;
        document.getElementById('presenter').classList.remove('readonly')
    } else {
        document.getElementById('title').value = talkdata[e.value]["title"]
        document.getElementById('title').readOnly = true;
        document.getElementById('title').classList.add('readonly')
        document.getElementById('presenter').value = talkdata[e.value]["presenter"]
        document.getElementById('presenter').readOnly = true;
        document.getElementById('presenter').classList.add('readonly')
        document.getElementById('talkid').value = e.value
        document.getElementById('talkid').readOnly = true;
        document.getElementById('talkid').classList.add('readonly')
    }
}