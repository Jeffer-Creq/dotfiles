from dbus_next.constants import MessageType

from libqtile.log_utils import logger
from libqtile.utils import add_signal_receiver
from libqtile.widget import base
import psutil


class Spotify(base.ThreadPoolText):
    """An MPRIS 2 widget mod
        A modification of the Mpris2 widget so that the text always keeps scrolling
    """

    defaults = [
        ("name", "audacious", "Name of the MPRIS widget."),
        (
            "objname",
            "org.mpris.MediaPlayer2.audacious",
            "DBUS MPRIS 2 compatible player identifier"
            "- Find it out with dbus-monitor - "
            "Also see: http://specifications.freedesktop.org/"
            "mpris-spec/latest/#Bus-Name-Policy",
        ),
        (
            "display_metadata",
            ["xesam:title", "xesam:album", "xesam:artist"],
            "Which metadata identifiers to display. "
            "See http://www.freedesktop.org/wiki/Specifications/mpris-spec/metadata/#index5h3 "
            "for available values",
        ),
        ("scroll_chars", 30, "How many chars at once to display."),
        ("scroll_interval", 0.5, "Scroll delay interval."),
        ("scroll_wait_intervals", 8, "Wait x scroll_interval before" "scrolling/removing text"),
        ("stop_pause_text", None, "Optional text to display when in the stopped/paused state"),
    ]

    def __init__(self, **config):
        base.ThreadPoolText.__init__(self, "", **config)
        self.add_defaults(Spotify.defaults)

        self.scrolltext = None
        self.displaytext = ""
        self.is_playing = False
        self.scroll_timer = None
        self.scroll_counter = None
        self.count = 0

    async def _config_async(self):
        subscribe = await add_signal_receiver(
            self.message,
            session_bus=True,
            signal_name="PropertiesChanged",
            bus_name=self.objname,
            path="/org/mpris/MediaPlayer2",
            dbus_interface="org.freedesktop.DBus.Properties",
        )

        if not subscribe:
            msg = "Unable to add signal receiver for {}.".format(self.objname)
            logger.warning(msg)

    def message(self, message):
        if message.message_type != MessageType.SIGNAL:
            return

        self.update(*message.body)

    def update(self, interface_name, changed_properties, _invalidated_properties):
        """
        http://specifications.freedesktop.org/mpris-spec/latest/Track_List_Interface.html#Mapping:Metadata_Map
        """
        if not self.configured:
            return True
        olddisplaytext = self.displaytext
        self.displaytext = ""

        metadata = changed_properties.get("Metadata")
        if metadata:
            metadata = metadata.value
            self.is_playing = True

            meta_list = []
            for key in self.display_metadata:
                val = getattr(metadata.get(key), "value", None)
                if isinstance(val, str):
                    meta_list.append(val)
                elif isinstance(val, list):
                    val = " - ".join((y for y in val if isinstance(y, str)))
                    meta_list.append(val)

            self.displaytext = " - ".join(meta_list)
            self.displaytext.replace("\n", "")

        playbackstatus = getattr(changed_properties.get("PlaybackStatus"), "value", None)
        if playbackstatus == "Paused":
            if self.stop_pause_text is not None:
                self.is_playing = False
                self.displaytext = self.stop_pause_text
            elif self.displaytext:
                self.is_playing = False
                self.displaytext = "Paused: {}".format(self.displaytext)
            else:
                self.is_playing = False
                self.displaytext = "Paused"
        elif playbackstatus == "Playing":
            if not self.displaytext and olddisplaytext:
                self.is_playing = True
                self.displaytext = olddisplaytext.replace("Paused: ", "")
            elif not self.displaytext and not olddisplaytext:
                self.is_playing = True
                self.displaytext = "No metadata for current track"
            elif self.displaytext:
                # Players might send more than one "Playing" message.
                pass
        elif playbackstatus:
            self.is_playing = False
            self.displaytext = ""

        if self.scroll_chars and self.scroll_interval:
            if self.scroll_timer:
                self.scroll_timer.cancel()
            if self.displaytext:
                self.scrolltext = self.displaytext + "  "
            else:
                self.scrolltext = self.displaytext
            self.scroll_counter = self.scroll_wait_intervals
            self.scroll_timer = self.timeout_add(self.scroll_interval, self.scroll_text)
            return
        if self.text != self.displaytext:
            self.text = self.displaytext
            self.bar.draw()

    def scroll_text(self):
        if len(self.displaytext) < self.scroll_chars:
            self.text = self.displaytext
            self.bar.draw()
            return
        if self.text != self.scrolltext[: self.scroll_chars]:
            self.text = self.scrolltext[: self.scroll_chars]
            self.bar.draw()
            self.scrolltext = self.scrolltext[1:] + self.scrolltext[0]
        if self.is_playing:
            if self.scroll_timer:
                self.scroll_timer.cancel()
            self.scroll_timer = self.timeout_add(self.scroll_interval, self.scroll_text)
            return
        else:
            self.text = ""
            self.bar.draw()
            return 

    def cmd_info(self):
        """What's the current state of the widget?"""
        return dict(
            displaytext=self.displaytext,
            isplaying=self.is_playing,
        ) 

class SpotifyIcon(base.ThreadPoolText):
    defaults = [
        ("update_interval", 2, "Update time in seconds."),  # This arg is necessary
    ]

    def __init__(self, **config):
        base.ThreadPoolText.__init__(self, "", **config)
        self.add_defaults(SpotifyIcon.defaults)
        self.icon=''
        self.last_session_cur = {}

    def poll(self):
        if ("spotify" in (i.name() for i in psutil.process_iter())):
            return self.icon
        else:
            return ''


