import pandera.pandas as pa
from pandera.typing import Series


class RawBikeDataSchema(pa.DataFrameModel):
    """Schema for raw bike sharing data with strict validation.

    All constraints enforce valid data ranges and prevent arbitrary values.
    """

    # Optional datetime column (present in raw data, dropped during preprocessing)
    datetime: Series[str] = pa.Field(
        nullable=True, description="Datetime string (optional)"
    )
    season: Series[int] = pa.Field(ge=1, le=4, description="Season (1-4)")
    yr: Series[int] = pa.Field(ge=0, le=1, description="Year (0-1: 2011-2012)")
    mnth: Series[int] = pa.Field(ge=1, le=12, description="Month (1-12)")
    hr: Series[int] = pa.Field(ge=0, le=23, description="Hour (0-23)")
    holiday: Series[int] = pa.Field(isin=[0, 1], description="Holiday flag")
    weekday: Series[int] = pa.Field(ge=0, le=6, description="Day of week (0-6)")
    workingday: Series[int] = pa.Field(isin=[0, 1], description="Working day flag")
    weathersit: Series[int] = pa.Field(ge=1, le=4, description="Weather (1-4)")
    temp: Series[float] = pa.Field(
        ge=0.0, le=1.0, description="Temperature (normalized 0-1)"
    )
    atemp: Series[float] = pa.Field(
        ge=0.0, le=1.0, description="Felt temperature (normalized 0-1)"
    )
    hum: Series[float] = pa.Field(
        ge=0.0, le=1.0, description="Humidity (normalized 0-1)"
    )
    windspeed: Series[float] = pa.Field(
        ge=0.0, le=1.0, description="Wind speed (normalized 0-1)"
    )
    casual: Series[int] = pa.Field(ge=0, description="Casual user count")
    registered: Series[int] = pa.Field(ge=0, description="Registered user count")
    cnt: Series[int] = pa.Field(ge=0, description="Total bike rental count")

    class Config:
        """Pandera configuration for demand data schema.

        Settings:
        - strict: Reject extra columns, require exact schema match
        - coerce: Enable type coercion for numeric types
        """

        # STRICT mode: reject extra columns, require exact schema match
        strict = True
        # Enable type coercion only for numeric types
        coerce = True
