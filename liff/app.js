const API = "https://the-3rd-space-webhook-36728838709.asia-northeast1.run.app"

let userId = null
let role = null

async function init() {

    await liff.init({
        liffId: "LIFF_ID_HERE"
    })

    const profile = await liff.getProfile()

    userId = profile.userId

    checkStatus()

}

async function checkStatus() {

    const res = await fetch(API + "/liff/status", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            userId: userId
        })
    })

    const data = await res.json()

    document.getElementById("loading").classList.add("hidden")

    if (!data.registered) {

        document.getElementById("register").classList.remove("hidden")

    } else {

        role = data.role

        showSubmit(data)

    }

}

function showSubmit(data) {

    document.getElementById("submit").classList.remove("hidden")

    document.getElementById("roleLabel").innerText =
        role === "husband" ? "あなたは夫です" : "あなたは妻です"

}

document.getElementById("registerBtn").onclick = async () => {

    const passphrase =
        document.getElementById("passphrase").value

    const res = await fetch(API + "/liff/register", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            userId: userId,
            passphrase: passphrase
        })

    })

    const data = await res.json()

    if (data.ok) {

        role = data.role

        document.getElementById("register").classList.add("hidden")

        showSubmit(data)

    } else {

        alert("登録できません")

    }

}

document.getElementById("submitBtn").onclick = async () => {

    const text =
        document.getElementById("message").value

    await fetch(API + "/liff/submit", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            userId: userId,
            text: text
        })

    })

    alert("提出しました")

}
 
init()