"""数据模型定义

所有模块间传递的数据结构集中定义，确保类型安全和接口一致性。
"""

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    DETECTING = "detecting"
    SEGMENTING = "segmenting"
    FUSING = "fusing"
    DONE = "done"
    ERROR = "error"


class WordTimestamp(BaseModel):
    """Whisper 字级时间戳"""

    word: str = Field(..., description="识别的文字")
    start: float = Field(..., ge=0, description="开始时间（秒）")
    end: float = Field(..., ge=0, description="结束时间（秒）")

    @model_validator(mode="after")
    def validate_time_range(self) -> "WordTimestamp":
        if self.start > self.end:
            raise ValueError("start 不能大于 end")
        return self


class TranscribedSegment(BaseModel):
    """Whisper 段落级转写片段（语音停顿边界）"""

    text: str = Field(..., description="该段落文字内容")
    start: float = Field(..., ge=0, description="段落开始时间（秒）")
    end: float = Field(..., ge=0, description="段落结束时间（秒）")

    @model_validator(mode="after")
    def validate_time_range(self) -> "TranscribedSegment":
        if self.start > self.end:
            raise ValueError("start 不能大于 end")
        return self


class WhisperResult(BaseModel):
    """Whisper 完整转写结果"""

    text: str = Field("", description="全文文字")
    segments: list[WordTimestamp] = Field(
        default_factory=list, description="字级时间戳列表"
    )
    paragraphs: list[TranscribedSegment] = Field(
        default_factory=list, description="段落级转写片段（语音停顿边界）"
    )
    duration: float = Field(0.0, ge=0, description="音频总时长（秒）")


class SceneCut(BaseModel):
    """PySceneDetect 场景切点"""

    time: float = Field(..., ge=0, description="切点时间（秒）")
    frame: int = Field(..., ge=0, description="切点帧号")


class SceneCutsResult(BaseModel):
    """场景检测结果"""

    cuts: list[SceneCut] = Field(
        default_factory=list, description="场景切点列表"
    )
    total_frames: int = Field(0, ge=0, description="视频总帧数")


class SemanticSegment(BaseModel):
    """DeepSeek 语义分镜"""

    index: int = Field(..., ge=0, description="分镜序号")
    summary: str = Field(..., description="分镜内容摘要")
    start_text: str = Field(..., description="分镜起始文字片段")
    end_text: str = Field(..., description="分镜结束文字片段")


class SemanticResult(BaseModel):
    """语义分镜结果"""

    segments: list[SemanticSegment] = Field(
        default_factory=list, description="语义分镜列表"
    )

    @model_validator(mode="after")
    def validate_sequential_indices(self) -> "SemanticResult":
        """验证分镜 index 从 0 开始连续递增"""
        for i, seg in enumerate(self.segments):
            if seg.index != i:
                raise ValueError(
                    f"分镜 index 必须从 0 开始连续递增，预期 {i}，实际 {seg.index}"
                )
        return self


class FusedScene(BaseModel):
    """融合后的最终分镜"""

    index: int = Field(..., ge=0, description="分镜序号")
    start_time: float = Field(..., ge=0, description="开始时间（秒）")
    end_time: float = Field(..., ge=0, description="结束时间（秒）")
    summary: str = Field("", description="分镜摘要")
    text: str = Field("", description="分镜对应的文字内容")
    has_scene_cut: bool = Field(
        False, description="边界是否有画面切点"
    )

    @model_validator(mode="after")
    def validate_time_range(self) -> "FusedScene":
        if self.start_time > self.end_time:
            raise ValueError("start_time 不能大于 end_time")
        return self


class TaskResult(BaseModel):
    """任务完整输出结果"""

    task_id: str = Field(..., description="任务唯一标识")
    status: TaskStatus = Field(..., description="任务状态")
    title: str = Field("", description="视频标题")
    url: str = Field("", description="原始视频链接")
    scenes: list[FusedScene] = Field(
        default_factory=list, description="融合分镜列表"
    )
    error_message: str | None = Field(
        None, description="错误信息（仅 status=ERROR 时有值）"
    )


class BatchResult(BaseModel):
    """批量处理结果"""

    total: int = Field(0, description="总任务数")
    succeeded: int = Field(0, description="成功数")
    failed: int = Field(0, description="失败数")
    total_duration: float = Field(0.0, description="所有视频总时长（秒）")
    results: list[TaskResult] = Field(
        default_factory=list, description="各任务结果列表"
    )
