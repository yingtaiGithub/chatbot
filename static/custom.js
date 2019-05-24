// Initialise Pusher
const pusher = new Pusher('9a594e7b230425615180', {
    cluster: 'ap3',
    encrypted: true
});

// Subscribe to movie_bot channel
const channel = pusher.subscribe('calendar bot-development');

// bind new_message event to movie_bot channel
channel.bind('new_message', function(data) {
    console.log(data)
    // Append human message
    $('.chat-container').append(`
        <div class="chat-message col-md-5 human-message">
            ${data.human_message}
        </div>
    `)
    
    // Append bot message
    $('.chat-container').append(`
        <div class="chat-message col-md-5 offset-md-7 bot-message">
        ${data.bot_message}
        </div>
    `)
});

function offset(el) {
    var rect = el.getBoundingClientRect(),
    scrollLeft = window.pageXOffset || document.documentElement.scrollLeft,
    scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    return { top: rect.top + scrollTop, left: rect.left + scrollLeft }
}

function placeDiv(d, x_pos, y_pos) {
  d.style.display = 'block';
  d.style.position = "absolute";
  d.style.left = x_pos+'px';
  d.style.top = y_pos+'px';
}

$(function() {
    $('.chat-container').append(`
        <div class="chat-message col-md-5 offset-md-7 bot-message">
            Hey there! I\'ll help you book a meeting with $USER. But first where should I sent the invitation to?
        </div>
    `)

    function submit_message(message) {
        $.post( "/send_message", {
            message: message, 
            socketId: pusher.connection.socket_id,
        }, handle_response);
        
        function handle_response(data) {
            // append the bot repsonse to the div
            var message_array = data.message.split(";")
            console.log(data.message)
            $('.chat-container').append(`
                <div class="chat-message col-md-5 offset-md-7 bot-message">
                    ${message_array[0]}
                </div>
            `)

            if (message_array.length == 2) {
                var d = document.getElementById(message_array[1]);
                placeDiv(d, $('#input_message').position().left, $('#input_message').position().top)
            } else if (message_array.length == 3) {
                var d = document.getElementById(message_array[1]);
                var contents = message_array[2].split(",");
                for (var i = 0; i < contents.length; i++) {
                    var button_string = '<button>'+ contents[i] + '</button>'
                    $('#' +message_array[1]).append(button_string)
                }

                placeDiv(d, $('#input_message').position().left, $('#input_message').position().top)
            }
            // remove the loading indicator
            $( "#loading" ).remove();
        }
    }

    $('#target').on('submit', function(e){
        e.preventDefault();
        const input_message = $('#input_message').val()
        // return if the user does not enter any text
        if (!input_message) {
            return
        }
        
        $('.chat-container').append(`
            <div class="chat-message col-md-5 human-message">
                ${input_message}
            </div>
        `)
        
        // loading 
        $('.chat-container').append(`
            <div class="chat-message text-center col-md-2 offset-md-10 bot-message" id="loading">
                <b>...</b>
            </div>
        `)
        
        // clear the text input 
        $('#input_message').val('')
        
        // send the message
        submit_message(input_message)
    });

    $(".selector").on('click', 'button', function(){
        var message = $(this).text();
        $(this).parent().hide();
        $('.chat-container').append(`
            <div class="chat-message col-md-5 human-message">
                ${message}
            </div>
        `)

        $('.chat-container').append(`
            <div class="chat-message text-center col-md-2 offset-md-10 bot-message" id="loading">
                <b>...</b>
            </div>
        `)

        submit_message(message)
    })

    $('#select1 select').change(function(){
        var message = $('#select1 select :selected').text();
        var timezone = $('#select1 select').val();
        $(this).parent().hide();

        $('.chat-container').append(`
            <div class="chat-message col-md-5 human-message">
                ${message}
            </div>
        `)

        $('.chat-container').append(`
            <div class="chat-message text-center col-md-2 offset-md-10 bot-message" id="loading">
                <b>...</b>
            </div>
        `)

        submit_message(timezone+";timezone")

    });
});