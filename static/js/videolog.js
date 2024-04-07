var framerate = 25

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
    if (mins > 60){
        mins = 60
    }
    var secs = parseInt(time_array[3])
    if (secs > 60) {
        secs = 60
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

function updateTC(now, meta) {
    var frames = seconds_to_timestamp(meta.mediaTime)
    document.getElementById("inputtc").value = frames
    document.getElementById("video1").requestVideoFrameCallback(updateTC)
};

function frameevent() {
    document.getElementById("video1").requestVideoFrameCallback(updateTC)
}

function checkKey(e) {
    e = e || window.event;
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

window.onload = frameevent

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

function display_help() {

}