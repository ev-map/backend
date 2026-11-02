# class Datex2LithuaniaDataSource(BaseDatex2DataSource):
#     id = "lithuania"
#     license_attribution = "Via Lietuva, CC-BY 4.0"
#     # https://ev.vialietuva.lt/en/data-provision
#
#     def get_data(self) -> str:
#         response = requests.get(
#             "https://ev.vialietuva.lt/publicdata/EnergyInfrastructureTablePublication",
#         )
#         response.raise_for_status()
#         return response.text
