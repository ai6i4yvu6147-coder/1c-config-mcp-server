import os
import xml.etree.ElementTree as ET

from .xml_helpers import _winlong


class FlowchartMixin:
    """Business process flowchart parsing (route points and transitions)."""

    def _parse_flowchart(self, name, folder_name):
        """Точки маршрута и переходы бизнес-процесса из Ext/Flowchart.xml."""
        flowchart_path = self.root_dir / folder_name / name / 'Ext' / 'Flowchart.xml'
        empty = {'route_points': [], 'route_transitions': []}
        if not os.path.exists(_winlong(flowchart_path)):
            return empty

        sch_ns = 'http://v8.1c.ru/8.3/xcf/scheme'
        tree = ET.parse(_winlong(flowchart_path))
        root = tree.getroot()
        items = root.find(f'{{{sch_ns}}}Items')
        if items is None:
            return empty

        route_points = []
        route_transitions = []
        for child in items:
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local_tag == 'ConnectionLine':
                transition = self._parse_flowchart_transition(child, sch_ns)
                if transition:
                    route_transitions.append(transition)
                continue
            point = self._parse_flowchart_point(child, local_tag, sch_ns)
            if point:
                route_points.append(point)

        return {'route_points': route_points, 'route_transitions': route_transitions}

    def _parse_flowchart_point(self, elem, point_type, sch_ns):
        """Одна точка маршрута (Start, Activity, Condition, …)."""
        props = elem.find(f'{{{sch_ns}}}Properties')
        if props is None:
            return None
        name_elem = props.find(f'{{{sch_ns}}}Name')
        point_name = name_elem.text.strip() if name_elem is not None and name_elem.text else ''
        if not point_name:
            return None

        tab_order = self._flowchart_int(props.find(f'{{{sch_ns}}}TabOrder'))
        point = {
            'name': point_name,
            'type': point_type,
            'title': self._extract_synonym(props),
            'uuid': elem.get('uuid', '') or '',
            'tab_order': tab_order,
            'true_port': None,
            'false_port': None,
            'group': None,
        }
        if point_type == 'Condition':
            point['true_port'] = self._flowchart_int(props.find(f'{{{sch_ns}}}TruePortIndex'))
            point['false_port'] = self._flowchart_int(props.find(f'{{{sch_ns}}}FalsePortIndex'))
        elif point_type == 'Activity':
            group_elem = props.find(f'{{{sch_ns}}}Group')
            if group_elem is not None and group_elem.text:
                point['group'] = group_elem.text.strip().lower() == 'true'
        return point

    def _parse_flowchart_transition(self, elem, sch_ns):
        """Переход между точками (ConnectionLine)."""
        props = elem.find(f'{{{sch_ns}}}Properties')
        if props is None:
            return None
        decorative = props.find(f'{{{sch_ns}}}DecorativeLine')
        if decorative is not None and decorative.text and decorative.text.strip().lower() == 'true':
            return None
        connect = props.find(f'{{{sch_ns}}}Connect')
        if connect is None:
            return None
        from_elem = connect.find(f'{{{sch_ns}}}From')
        to_elem = connect.find(f'{{{sch_ns}}}To')
        if from_elem is None or to_elem is None:
            return None
        from_item = from_elem.find(f'{{{sch_ns}}}Item')
        to_item = to_elem.find(f'{{{sch_ns}}}Item')
        if from_item is None or to_item is None or not from_item.text or not to_item.text:
            return None
        from_port_elem = from_elem.find(f'{{{sch_ns}}}PortIndex')
        return {
            'from': from_item.text.strip(),
            'to': to_item.text.strip(),
            'from_port': self._flowchart_int(from_port_elem),
            'title': self._extract_synonym(props),
        }

    def _flowchart_int(self, elem):
        if elem is None or not elem.text:
            return None
        try:
            return int(elem.text.strip())
        except ValueError:
            return None
