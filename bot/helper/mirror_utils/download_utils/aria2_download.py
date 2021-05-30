from bot import aria2, download_dict_lock, STOP_DUPLICATE_MIRROR, MAX_TORRENT_SIZE, ENABLE_FILESIZE_LIMIT
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.bot_utils import *
from .download_helper import DownloadHelper
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import *
import threading
from aria2p import API
from time import sleep


class AriaDownloadHelper(DownloadHelper):

    def __init__(self):
        super().__init__()

    @new_thread
    def __onDownloadStarted(self, api, gid):
        sleep(1)
        LOGGER.info(f"onDownloadStart: {gid}")
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        self.name = download.name
        sname = download.name
        if STOP_DUPLICATE_MIRROR:
          if dl.getListener().isTar == True:
            sname = sname + ".tar"
          if dl.getListener().extract == True:
            smsg = None
          else:
            gdrive = GoogleDriveHelper(None)
            smsg, button = gdrive.drive_list(sname)
          if smsg:
              dl.getListener().onDownloadError(f'File is already available in Drive.\n\n')
              sendMarkup("Here are the search results:", dl.getListener().bot, dl.getListener().update, button)
              aria2.remove([download])
              return

        size = download.total_length
        if ENABLE_FILESIZE_LIMIT:
          if size / 1024 / 1024 / 1024 > MAX_TORRENT_SIZE:
              LOGGER.info(f"Download size Exceeded: {gid}")
              dl.getListener().onDownloadError(f'📀 𝗬𝗼𝘂𝗿 𝗙𝗶𝗹𝗲 𝘀𝗶𝘇𝗲: {get_readable_file_size(size)}\n\n📛 𝗠𝗮𝘅𝗶𝗺𝘂𝗺 𝗠𝗶𝗿𝗿𝗼𝗿 𝗟𝗶𝗺𝗶𝘁: {MAX_TORRENT_SIZE}GB')
              aria2.remove([download])
              return
        update_all_messages()

    def __onDownloadComplete(self, api: API, gid):
        LOGGER.info(f"onDownloadComplete: {gid}")
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        if download.followed_by_ids:
            new_gid = download.followed_by_ids[0]
            new_download = api.get_download(new_gid)
            with download_dict_lock:
                download_dict[dl.uid()] = AriaDownloadStatus(new_gid, dl.getListener())
                if new_download.is_torrent:
                    download_dict[dl.uid()].is_torrent = True
            update_all_messages()
            LOGGER.info(f'Changed gid from {gid} to {new_gid}')
        else:
            if dl:
                threading.Thread(target=dl.getListener().onDownloadComplete).start()

    @new_thread
    def __onDownloadPause(self, api, gid):
        LOGGER.info(f"onDownloadPause: {gid}")
        dl = getDownloadByGid(gid)
        dl.getListener().onDownloadError('𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝘀𝘁𝗼𝗽𝗽𝗲𝗱 𝗯𝘆 𝘂𝘀𝗲𝗿!')

    @new_thread
    def __onDownloadStopped(self, api, gid):
        LOGGER.info(f"onDownloadStop: {gid}")
        dl = getDownloadByGid(gid)
        if dl: dl.getListener().onDownloadError('𝘠𝘰𝘶𝘳 𝘓𝘪𝘯𝘬 𝘪𝘴 𝘋𝘦𝘢𝘥. 𝘗𝘭𝘻 𝘥𝘰𝘯𝘵 𝘮𝘪𝘳𝘳𝘰𝘳 𝘭𝘰𝘸 𝘚𝘌𝘌𝘋𝘚 𝘵𝘰𝘳𝘳𝘦𝘯𝘵')

    @new_thread
    def __onDownloadError(self, api, gid):
        sleep(0.5)  # sleep for split second to ensure proper dl gid update from onDownloadComplete
        LOGGER.info(f"onDownloadError: {gid}")
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        error = download.error_message
        LOGGER.info(f"Download Error: {error}")
        if dl: dl.getListener().onDownloadError(error)

    def start_listener(self):
        aria2.listen_to_notifications(threaded=True, on_download_start=self.__onDownloadStarted,
                                      on_download_error=self.__onDownloadError,
                                      on_download_pause=self.__onDownloadPause,
                                      on_download_stop=self.__onDownloadStopped,
                                      on_download_complete=self.__onDownloadComplete)

    def add_download(self, link: str, path, listener, filename):
        if is_magnet(link):
            download = aria2.add_magnet(link, {'dir': path, 'out': filename})
        else:
            download = aria2.add_uris([link], {'dir': path, 'out': filename})
        if download.error_message:  # no need to proceed further at this point
            listener.onDownloadError(download.error_message)
            return
        with download_dict_lock:
            download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
            LOGGER.info(f"Started: {download.gid} DIR:{download.dir} ")
