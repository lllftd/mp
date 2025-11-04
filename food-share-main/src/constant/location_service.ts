import areaList from './area.js'
export function getProvinces() {
    let province = []
    for (const provinceKey in areaList.province_list) {
        province.push({
            label: areaList.province_list[provinceKey],
            value: areaList.province_list[provinceKey],
            code: provinceKey.substr(0,2),
            id: provinceKey.substr(0,2)
        })
    }

    return province;
}

export function getCitiesOf(provinceCode) {
    let cities = []
    for (const cityKey in areaList.city_list) {
        cities.push({
            name:areaList.city_list[cityKey],
            code: cityKey.substr(0,4),
            provinceCode:cityKey.substr(0,2),
        })
    }

    return cities.filter(c => c['provinceCode'] == provinceCode).map(city => {
        return {
            label: city.name,
            value: city.name,
            code: city.code,
            id: city.code
        }
    });
}

export function getAreasOf(cityCode) {
    let areas = []
    for (const areaKey in areaList.county_list) {
        areas.push({
            name: areaList.county_list[areaKey],
            code: areaKey,
            cityCode: areaKey.substr(0,4),
            provinceCode: areaKey.substr(0,2)
        })

    }
    return areas.filter(area => area['cityCode'] === cityCode).map(area => {
        return {
            label: area.name,
            value: area.name,
            code: area.code,
            id: area.code
        }
    });
}