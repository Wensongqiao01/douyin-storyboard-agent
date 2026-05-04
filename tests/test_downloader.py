"""测试视频下载双引擎"""
from unittest.mock import MagicMock, patch

import pytest

from core.downloader import (
    DouyinDownloaderEngine,
    YtDlpEngine,
    download_video,
)


class TestDouyinDownloaderEngine:
    """测试抖音下载器引擎"""

    @patch("core.downloader.DouyinDownloaderEngine.DOUYIN_SCRIPT")
    @patch("core.downloader.subprocess.run")
    def test_successful_download(
        self,
        mock_run: MagicMock,
        mock_script: MagicMock,
        tmp_path,
    ):
        """测试 douyin-downloader 成功下载"""
        output_path = str(tmp_path / "video.mp4")
        mock_script.exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        engine = DouyinDownloaderEngine()
        result = engine.download(
            "https://v.douyin.com/test", output_path, cookie="test_cookie"
        )

        assert result == output_path
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "python" in args[0]

    @patch("core.downloader.DouyinDownloaderEngine.DOUYIN_SCRIPT")
    @patch("core.downloader.subprocess.run")
    def test_failure_raises(
        self,
        mock_run: MagicMock,
        mock_script: MagicMock,
        tmp_path,
    ):
        """测试 douyin-downloader 失败时抛出异常"""
        output_path = str(tmp_path / "video.mp4")
        mock_script.exists.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        engine = DouyinDownloaderEngine()
        with pytest.raises(RuntimeError, match="douyin-downloader 下载失败"):
            engine.download(
                "https://v.douyin.com/test", output_path, cookie=""
            )

    @patch("core.downloader.DouyinDownloaderEngine.DOUYIN_SCRIPT")
    def test_missing_script_raises(
        self,
        mock_script: MagicMock,
        tmp_path,
    ):
        """测试 douyin-downloader 脚本不存在时抛出异常"""
        output_path = str(tmp_path / "video.mp4")
        mock_script.exists.return_value = False

        engine = DouyinDownloaderEngine()
        with pytest.raises(RuntimeError, match="douyin-downloader 脚本不存在"):
            engine.download(
                "https://v.douyin.com/test", output_path, cookie=""
            )


class TestYtDlpEngine:
    """测试 yt-dlp 降级引擎"""

    @patch("core.downloader.yt_dlp")
    def test_successful_download(self, mock_ytdlp: MagicMock, tmp_path):
        """测试 yt-dlp 成功下载"""
        output_path = str(tmp_path / "video.mp4")
        mock_ctx = MagicMock()
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value = mock_ctx

        engine = YtDlpEngine()
        result = engine.download(
            "https://v.douyin.com/test", output_path, cookie="test_cookie"
        )

        assert result == output_path
        mock_ctx.download.assert_called_once_with(
            ["https://v.douyin.com/test"]
        )

    @patch("core.downloader.yt_dlp")
    def test_failure_raises(self, mock_ytdlp: MagicMock, tmp_path):
        """测试 yt-dlp 下载失败时抛出异常"""
        output_path = str(tmp_path / "video.mp4")
        mock_ytdlp.YoutubeDL.side_effect = Exception("network error")

        engine = YtDlpEngine()
        with pytest.raises(RuntimeError, match="yt-dlp 下载失败"):
            engine.download(
                "https://v.douyin.com/test", output_path, cookie=""
            )

    @patch("core.downloader.yt_dlp", None)
    def test_missing_ytdlp_raises(self, tmp_path):
        """测试 yt-dlp 未安装时抛出异常"""
        output_path = str(tmp_path / "video.mp4")

        engine = YtDlpEngine()
        with pytest.raises(RuntimeError, match="yt-dlp 未安装"):
            engine.download(
                "https://v.douyin.com/test", output_path, cookie=""
            )


class TestDownloadVideo:
    """测试 download_video 入口函数"""

    @patch("core.downloader.DouyinDownloaderEngine.download")
    def test_primary_engine_success(self, mock_primary: MagicMock, tmp_path):
        """测试主引擎 douyin-downloader 成功"""
        output_path = str(tmp_path / "video.mp4")
        mock_primary.return_value = output_path

        result = download_video(
            url="https://v.douyin.com/test",
            output_path=output_path,
            cookie="test_cookie",
        )

        assert result == output_path
        mock_primary.assert_called_once()

    @patch("core.downloader.DouyinDownloaderEngine.download")
    @patch("core.downloader.YtDlpEngine.download")
    def test_fallback_on_primary_failure(
        self,
        mock_fallback: MagicMock,
        mock_primary: MagicMock,
        tmp_path,
    ):
        """测试主引擎失败时自动降级到 yt-dlp"""
        output_path = str(tmp_path / "video.mp4")
        mock_primary.side_effect = RuntimeError("primary failed")
        mock_fallback.return_value = output_path

        result = download_video(
            url="https://v.douyin.com/test",
            output_path=output_path,
            cookie="test_cookie",
        )

        assert result == output_path
        mock_primary.assert_called_once()
        mock_fallback.assert_called_once()

    @patch("core.downloader.DouyinDownloaderEngine.download")
    @patch("core.downloader.YtDlpEngine.download")
    def test_both_engines_fail(
        self,
        mock_fallback: MagicMock,
        mock_primary: MagicMock,
    ):
        """测试两个引擎都失败时抛出异常"""
        mock_primary.side_effect = RuntimeError("primary failed")
        mock_fallback.side_effect = RuntimeError("fallback failed")

        with pytest.raises(RuntimeError, match="所有下载引擎均失败"):
            download_video(
                url="https://v.douyin.com/test",
                output_path="/tmp/video.mp4",
                cookie="",
            )

    @patch("core.downloader.DouyinDownloaderEngine.download")
    def test_empty_url_raises(self, mock_primary: MagicMock):
        """测试空 URL 抛出异常"""
        with pytest.raises(ValueError, match="URL 不能为空"):
            download_video(
                url="", output_path="/tmp/video.mp4", cookie=""
            )

    @patch("core.downloader.DouyinDownloaderEngine.download")
    def test_empty_output_path_raises(self, mock_primary: MagicMock):
        """测试空输出路径抛出异常"""
        with pytest.raises(ValueError, match="输出路径不能为空"):
            download_video(
                url="https://v.douyin.com/test", output_path="", cookie=""
            )

    @patch("core.downloader.DouyinDownloaderEngine.download")
    def test_default_cookie_from_config(
        self, mock_primary: MagicMock, tmp_path
    ):
        """测试 cookie 默认从 config 读取"""
        output_path = str(tmp_path / "video.mp4")
        mock_primary.return_value = output_path

        download_video(
            url="https://v.douyin.com/test",
            output_path=output_path,
        )

        mock_primary.assert_called_once()
