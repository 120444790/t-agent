from sqlalchemy import String, Text, ForeignKey, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.base_model import BaseModel


class Department(BaseModel):
    """科室表"""
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False, comment="科室名称"
    )
    description: Mapped[str | None] = mapped_column(Text, comment="科室简介")


class Disease(BaseModel):
    """疾病表"""
    __tablename__ = "diseases"

    name: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False, comment="疾病名称"
    )
    description: Mapped[str | None] = mapped_column(Text, comment="疾病描述")
    cause: Mapped[str | None] = mapped_column(Text, comment="病因")
    prevent: Mapped[str | None] = mapped_column(Text, comment="预防措施")
    cure_lasttime: Mapped[str | None] = mapped_column(String(100), comment="治疗周期")
    cured_prob: Mapped[str | None] = mapped_column(String(200), comment="治愈概率")
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        index=True,
        comment="所属科室ID",
    )


class Symptom(BaseModel):
    """症状表"""
    __tablename__ = "symptoms"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False, comment="症状名称"
    )


class DiseaseSymptom(BaseModel):
    """疾病-症状 关联表（多对多）"""
    __tablename__ = "disease_symptoms"
    __table_args__ = (
        Index("ix_disease_symptom", "disease_id", "symptom_id", unique=True),
    )

    disease_id: Mapped[int] = mapped_column(
        ForeignKey("diseases.id", ondelete="CASCADE"), nullable=False
    )
    symptom_id: Mapped[int] = mapped_column(
        ForeignKey("symptoms.id", ondelete="CASCADE"), nullable=False
    )

class Drug(BaseModel):
    """药品表"""
    __tablename__ = "drugs"

    name: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False, comment="药品通用名"
    )
    stock_quantity: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="库存数量"
    )


class DrugDetail(BaseModel):
    """药品说明书（垂直拆表，避免列表查询加载大文本）"""
    __tablename__ = "drug_details"

    drug_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="关联药品ID",
    )
    indication: Mapped[str | None] = mapped_column(Text, comment="功能主治")
    usage: Mapped[str | None] = mapped_column(Text, comment="用法用量")
    contraindication: Mapped[str | None] = mapped_column(Text, comment="禁忌")
    side_effect: Mapped[str | None] = mapped_column(Text, comment="不良反应")


class DiseaseDrug(BaseModel):
    """疾病-药品 关联表"""
    __tablename__ = "disease_drugs"
    __table_args__ = (
        Index("ix_disease_drug", "disease_id", "drug_id", "relation_type", unique=True),
    )

    disease_id: Mapped[int] = mapped_column(
        ForeignKey("diseases.id", ondelete="CASCADE"), nullable=False
    )
    drug_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="common", comment="关系类型: common/recommend"
    )


class Patient(BaseModel):
    """患者表"""
    __tablename__ = "patients"

    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="患者姓名")
    gender: Mapped[str | None] = mapped_column(String(10), comment="性别")
    age: Mapped[int | None] = mapped_column(Integer, comment="年龄")
    phone: Mapped[str | None] = mapped_column(String(20), comment="联系电话")


class Consultation(BaseModel):
    """问诊记录表"""
    __tablename__ = "consultations"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="患者ID",
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        index=True,
        comment="建议科室ID",
    )
    chief_complaint: Mapped[str | None] = mapped_column(Text, comment="主诉")
    urgency_level: Mapped[str | None] = mapped_column(
        String(20), comment="紧急程度: low/medium/high"
    )